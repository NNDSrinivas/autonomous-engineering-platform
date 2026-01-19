"""
Linear webhook ingestion.

Handles Linear issue, comment, project, and cycle events.
Linear webhooks are signed using HMAC-SHA256.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/linear", tags=["linear_webhook"])
logger = logging.getLogger(__name__)


def verify_linear_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """Verify Linear webhook HMAC-SHA256 signature."""
    if not secret:
        logger.warning("linear_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing Linear-Signature header")

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("")
async def ingest(
    request: Request,
    linear_signature: Optional[str] = Header(None, alias="Linear-Signature"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Linear webhooks.

    Linear webhook events:
    - Issue (create, update, remove)
    - Comment (create, update, remove)
    - Project (create, update, remove)
    - Cycle (create, update, remove)
    """
    body = await request.body()
    verify_linear_signature(linear_signature, body, settings.linear_webhook_secret)

    payload = await request.json()

    action = payload.get("action") or "unknown"
    event_type = payload.get("type") or "unknown"
    org_id = x_org_id or settings.x_org_id

    try:
        if event_type == "Issue":
            await _handle_issue(payload, action, org_id, db)

        elif event_type == "Comment":
            await _handle_comment(payload, action, org_id, db)

        elif event_type == "Project":
            await _handle_project(payload, action, org_id, db)

        elif event_type == "Cycle":
            await _handle_cycle(payload, action, org_id, db)

        else:
            logger.info(
                "linear_webhook.unhandled_event",
                extra={"type": event_type, "action": action},
            )

    except Exception as exc:
        logger.error(
            "linear_webhook.error",
            extra={"type": event_type, "action": action, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_issue(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle issue events."""
    data = payload.get("data") or {}

    issue_id = data.get("id")
    identifier = data.get("identifier") or ""
    title = data.get("title") or ""
    description = data.get("description") or ""
    priority = data.get("priority") or 0
    priority_label = data.get("priorityLabel") or ""
    url = data.get("url") or ""

    state = data.get("state") or {}
    state_name = state.get("name") or "unknown"

    team = data.get("team") or {}
    team_name = team.get("name") or "unknown"

    assignee = data.get("assignee") or {}
    assignee_name = assignee.get("name") if assignee else None

    creator = data.get("creator") or {}
    creator_name = creator.get("name") or "unknown"

    node = MemoryNode(
        org_id=org_id,
        node_type="linear_issue",
        title=f"{identifier}: {title}",
        text=description[:500] if description else f"Issue {action} by {creator_name}",
        meta_json={
            "issue_id": issue_id,
            "identifier": identifier,
            "action": action,
            "state": state_name,
            "priority": priority,
            "priority_label": priority_label,
            "team": team_name,
            "assignee": assignee_name,
            "creator": creator_name,
            "url": url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "linear_webhook.issue",
        extra={
            "identifier": identifier,
            "action": action,
            "state": state_name,
        },
    )


async def _handle_comment(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle comment events."""
    data = payload.get("data") or {}

    comment_id = data.get("id")
    body = data.get("body") or ""
    url = data.get("url") or ""

    user = data.get("user") or {}
    user_name = user.get("name") or "unknown"

    issue = data.get("issue") or {}
    issue_identifier = issue.get("identifier") or ""
    issue_title = issue.get("title") or ""

    node = MemoryNode(
        org_id=org_id,
        node_type="linear_comment",
        title=f"Comment on {issue_identifier}: {issue_title[:50]}",
        text=body[:500],
        meta_json={
            "comment_id": comment_id,
            "action": action,
            "issue_identifier": issue_identifier,
            "issue_title": issue_title,
            "user": user_name,
            "url": url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "linear_webhook.comment",
        extra={
            "issue_identifier": issue_identifier,
            "action": action,
            "user": user_name,
        },
    )


async def _handle_project(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle project events."""
    data = payload.get("data") or {}

    project_id = data.get("id")
    name = data.get("name") or ""
    description = data.get("description") or ""
    state = data.get("state") or "unknown"
    progress = data.get("progress") or 0
    url = data.get("url") or ""

    lead = data.get("lead") or {}
    lead_name = lead.get("name") if lead else None

    node = MemoryNode(
        org_id=org_id,
        node_type="linear_project",
        title=f"Project: {name}",
        text=description[:500] if description else f"Project {action}",
        meta_json={
            "project_id": project_id,
            "name": name,
            "action": action,
            "state": state,
            "progress": progress,
            "lead": lead_name,
            "url": url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "linear_webhook.project",
        extra={
            "name": name,
            "action": action,
            "state": state,
        },
    )


async def _handle_cycle(
    payload: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle cycle (sprint) events."""
    data = payload.get("data") or {}

    cycle_id = data.get("id")
    name = data.get("name") or ""
    number = data.get("number") or 0
    starts_at = data.get("startsAt") or ""
    ends_at = data.get("endsAt") or ""
    progress = data.get("progress") or 0

    team = data.get("team") or {}
    team_name = team.get("name") or "unknown"

    node = MemoryNode(
        org_id=org_id,
        node_type="linear_cycle",
        title=f"Cycle {number}: {name}" if name else f"Cycle {number}",
        text=f"Cycle {action} for team {team_name}. Progress: {int(progress * 100)}%",
        meta_json={
            "cycle_id": cycle_id,
            "name": name,
            "number": number,
            "action": action,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "progress": progress,
            "team": team_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "linear_webhook.cycle",
        extra={
            "number": number,
            "action": action,
            "team": team_name,
        },
    )
