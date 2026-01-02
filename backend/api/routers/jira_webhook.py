"""
Jira webhook ingestion (read-side freshness for context packets)

Accepts Jira webhooks and upserts issues into the local cache.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.integrations import JiraConnection
from backend.models.memory_graph import MemoryNode, MemoryEdge
from backend.services.jira import JiraService
from backend.core.webhooks import verify_shared_secret
from backend.core.auth_org import require_org
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/jira", tags=["jira_webhook"])
logger = logging.getLogger(__name__)


def _extract_adf_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if value.get("type") == "text":
            return value.get("text", "")
        if "content" in value:
            return " ".join(_extract_adf_text(item) for item in value["content"])
    if isinstance(value, list):
        return " ".join(_extract_adf_text(item) for item in value)
    return str(value)


def _issue_node_payload(issue: Dict[str, Any], base_url: str | None) -> Dict[str, Any]:
    fields = issue.get("fields", {}) or {}
    issue_key = issue.get("key") or ""
    summary = fields.get("summary") or ""
    description_text = _extract_adf_text(fields.get("description"))
    issue_url = f"{base_url}/browse/{issue_key}" if base_url and issue_key else None

    text = "\n\n".join(part for part in [summary, description_text] if part).strip()
    if not text:
        text = issue_key

    return {
        "title": f"{issue_key}: {summary}".strip(": "),
        "text": text,
        "meta_json": {
            "issue_key": issue_key,
            "summary": summary,
            "status": (fields.get("status") or {}).get("name"),
            "priority": (fields.get("priority") or {}).get("name"),
            "assignee": (fields.get("assignee") or {}).get("displayName"),
            "reporter": (fields.get("reporter") or {}).get("displayName"),
            "issue_type": (fields.get("issuetype") or {}).get("name"),
            "project": (fields.get("project") or {}).get("key"),
            "url": issue_url,
            "updated": fields.get("updated"),
        },
    }


@router.post("/issue")
async def ingest_issue(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    org_ctx: dict = Depends(require_org),
):
    """
    Ingest Jira issue webhooks (created/updated).
    """
    verify_shared_secret(
        x_webhook_secret, settings.jira_webhook_secret, connector="jira"
    )

    issue = payload.get("issue")
    if not issue:
        raise HTTPException(status_code=400, detail="Missing issue payload")

    # Derive cloud base URL from issue.self
    self_url = issue.get("self") or ""
    base_url = self_url.split("/rest/")[0] if "/rest/" in self_url else None

    connection = None
    if base_url:
        query = db.query(JiraConnection).filter(
            JiraConnection.cloud_base_url == base_url
        )
        # Enforce org scoping
        query = query.filter(JiraConnection.org_id == org_ctx["org_id"])
        connection = query.order_by(JiraConnection.id.desc()).first()

    if not connection:
        logger.warning(
            "jira_webhook.no_connection",
            extra={"base_url": base_url, "issue_key": issue.get("key")},
        )
        raise HTTPException(
            status_code=202, detail="No Jira connection found for webhook base URL"
        )

    try:
        row = JiraService.upsert_issue(db, connection.id, issue)
        node_payload = _issue_node_payload(issue, base_url)
        node = MemoryNode(
            org_id=org_ctx["org_id"],
            node_type="jira_issue",
            title=node_payload["title"],
            text=node_payload["text"],
            meta_json=node_payload["meta_json"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(node)
        db.commit()

        invalidate_context_packet_cache(issue.get("key"), org_ctx["org_id"])
        return {"status": "ok", "issue_key": row.issue_key}
    except Exception as exc:
        logger.error("jira_webhook.upsert_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Failed to upsert issue: {exc}")


@router.post("/event")
async def ingest_event(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    org_ctx: dict = Depends(require_org),
):
    """
    Ingest Jira generic webhooks (comments, status changes).
    """
    verify_shared_secret(
        x_webhook_secret, settings.jira_webhook_secret, connector="jira"
    )

    issue = payload.get("issue") or {}
    issue_key = issue.get("key")
    if not issue_key:
        raise HTTPException(status_code=400, detail="Missing issue key")

    # Derive cloud base URL from issue.self
    self_url = issue.get("self") or ""
    base_url = self_url.split("/rest/")[0] if "/rest/" in self_url else None
    connection = None
    if base_url:
        query = db.query(JiraConnection).filter(
            JiraConnection.cloud_base_url == base_url
        )
        query = query.filter(JiraConnection.org_id == org_ctx["org_id"])
        connection = query.order_by(JiraConnection.id.desc()).first()

    if not connection:
        logger.warning(
            "jira_webhook.no_connection",
            extra={"base_url": base_url, "issue_key": issue_key},
        )
        raise HTTPException(
            status_code=202, detail="No Jira connection found for webhook base URL"
        )

    try:
        # Always upsert issue body to keep status fresh
        JiraService.upsert_issue(db, connection.id, issue)

        node_payload = _issue_node_payload(issue, base_url)
        issue_node = MemoryNode(
            org_id=org_ctx["org_id"],
            node_type="jira_issue",
            title=node_payload["title"],
            text=node_payload["text"],
            meta_json=node_payload["meta_json"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(issue_node)
        db.flush()

        # Comment added/updated
        if payload.get("comment"):
            comment = payload["comment"]
            JiraService.upsert_issue_comment(db, connection.id, issue_key, comment)

            comment_body = _extract_adf_text(comment.get("body"))
            comment_node = MemoryNode(
                org_id=org_ctx["org_id"],
                node_type="jira_comment",
                title=f"{issue_key} comment",
                text=comment_body or "",
                meta_json={
                    "issue_key": issue_key,
                    "comment_id": comment.get("id"),
                    "author": (comment.get("author") or {}).get("displayName"),
                    "created": comment.get("created"),
                    "updated": comment.get("updated"),
                    "url": comment.get("self"),
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(comment_node)
            db.flush()
            db.add(
                MemoryEdge(
                    org_id=org_ctx["org_id"],
                    from_id=comment_node.id,
                    to_id=issue_node.id,
                    edge_type="comments_on",
                    meta_json={"issue_key": issue_key},
                )
            )
        # Transition/status change captured via payload.transition
        if payload.get("transition"):
            trans = payload["transition"]
            logger.info(
                "jira_webhook.transition",
                extra={
                    "issue_key": issue_key,
                    "transition": trans.get("name"),
                    "id": trans.get("id"),
                },
            )

        db.commit()

        logger.info("jira_webhook.event_processed", extra={"issue_key": issue_key})
        invalidate_context_packet_cache(issue_key, org_ctx["org_id"])

        return {"status": "ok", "issue_key": issue_key}
    except Exception as exc:
        logger.error("jira_webhook.event_error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to process webhook event")
