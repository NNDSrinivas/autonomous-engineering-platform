"""
Jira webhook ingestion (read-side freshness for context packets)

Accepts Jira webhooks and upserts issues into the local cache.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.integrations import JiraConnection
from backend.services.jira import JiraService
from backend.core.webhooks import verify_shared_secret
from backend.core.auth_org import require_org
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/jira", tags=["jira_webhook"])
logger = logging.getLogger(__name__)


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

        # Comment added/updated
        if payload.get("comment"):
            JiraService.upsert_issue_comment(
                db, connection.id, issue_key, payload["comment"]
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

        logger.info("jira_webhook.event_processed", extra={"issue_key": issue_key})
        invalidate_context_packet_cache(issue_key, org_ctx["org_id"])

        return {"status": "ok", "issue_key": issue_key}
    except Exception as exc:
        logger.error("jira_webhook.event_error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to process webhook event")
