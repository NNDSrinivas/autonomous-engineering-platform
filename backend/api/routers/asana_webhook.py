"""
Asana webhook ingestion.

Handles Asana task, project, and story events.
Asana webhooks require X-Hook-Secret handshake and HMAC-SHA256 signature.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/asana", tags=["asana_webhook"])
logger = logging.getLogger(__name__)


def verify_asana_signature(
    signature: Optional[str],
    payload: bytes,
    secret: Optional[str],
) -> None:
    """Verify Asana webhook HMAC-SHA256 signature."""
    if not secret:
        logger.warning("asana_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Hook-Signature header")

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
    x_hook_secret: Optional[str] = Header(None, alias="X-Hook-Secret"),
    x_hook_signature: Optional[str] = Header(None, alias="X-Hook-Signature"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Asana webhooks.

    Asana webhook handshake:
    - Asana sends X-Hook-Secret header
    - We must respond with same value in X-Hook-Secret header

    Asana webhook events:
    - task: added, changed, deleted, undeleted
    - project: added, changed, deleted, undeleted
    - story: added, changed, deleted, undeleted
    """
    # Handle webhook handshake
    if x_hook_secret:
        logger.info("asana_webhook.handshake", extra={"secret": x_hook_secret[:8] + "..."})
        return Response(
            content="",
            status_code=200,
            headers={"X-Hook-Secret": x_hook_secret},
        )

    body = await request.body()
    verify_asana_signature(x_hook_signature, body, settings.asana_webhook_secret)

    payload = await request.json()
    events = payload.get("events") or []
    org_id = x_org_id or settings.x_org_id

    for event in events:
        try:
            resource_type = event.get("resource", {}).get("resource_type") or "unknown"
            action = event.get("action") or "unknown"

            if resource_type == "task":
                await _handle_task_event(event, action, org_id, db)
            elif resource_type == "project":
                await _handle_project_event(event, action, org_id, db)
            elif resource_type == "story":
                await _handle_story_event(event, action, org_id, db)
            else:
                logger.info(
                    "asana_webhook.unhandled_event",
                    extra={"resource_type": resource_type, "action": action},
                )

        except Exception as exc:
            logger.error(
                "asana_webhook.event_error",
                extra={
                    "resource_type": event.get("resource", {}).get("resource_type"),
                    "action": event.get("action"),
                    "error": str(exc),
                },
            )

    return {"status": "ok"}


async def _handle_task_event(
    event: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle task events."""
    resource = event.get("resource") or {}
    parent = event.get("parent") or {}
    user = event.get("user") or {}

    task_gid = resource.get("gid") or ""
    task_name = resource.get("name") or "Untitled Task"

    parent_gid = parent.get("gid") or ""
    parent_type = parent.get("resource_type") or ""
    parent_name = parent.get("name") or ""

    user_gid = user.get("gid") or ""
    user_name = user.get("name") or "Someone"

    # Change details
    change = event.get("change") or {}
    field = change.get("field") or ""
    new_value = change.get("new_value")
    change.get("action") or action

    # Build description
    if action == "added":
        text = f"{user_name} created task '{task_name}'"
        if parent_name:
            text += f" in {parent_type} '{parent_name}'"
    elif action == "changed":
        text = f"{user_name} updated task '{task_name}'"
        if field:
            text += f" ({field} changed)"
    elif action == "deleted":
        text = f"{user_name} deleted task '{task_name}'"
    elif action == "undeleted":
        text = f"{user_name} restored task '{task_name}'"
    else:
        text = f"Task '{task_name}' {action}"

    node = MemoryNode(
        org_id=org_id,
        node_type="asana_task",
        title=f"Asana Task: {task_name[:50]}",
        text=text,
        meta_json={
            "task_gid": task_gid,
            "task_name": task_name,
            "action": action,
            "field_changed": field,
            "new_value": str(new_value)[:200] if new_value else None,
            "parent_gid": parent_gid,
            "parent_type": parent_type,
            "parent_name": parent_name,
            "user_gid": user_gid,
            "user_name": user_name,
            "url": f"https://app.asana.com/0/0/{task_gid}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "asana_webhook.task",
        extra={
            "task_gid": task_gid,
            "action": action,
            "user": user_name,
        },
    )


async def _handle_project_event(
    event: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle project events."""
    resource = event.get("resource") or {}
    user = event.get("user") or {}

    project_gid = resource.get("gid") or ""
    project_name = resource.get("name") or "Untitled Project"

    user_gid = user.get("gid") or ""
    user_name = user.get("name") or "Someone"

    # Change details
    change = event.get("change") or {}
    field = change.get("field") or ""

    # Build description
    if action == "added":
        text = f"{user_name} created project '{project_name}'"
    elif action == "changed":
        text = f"{user_name} updated project '{project_name}'"
        if field:
            text += f" ({field} changed)"
    elif action == "deleted":
        text = f"{user_name} deleted project '{project_name}'"
    elif action == "undeleted":
        text = f"{user_name} restored project '{project_name}'"
    else:
        text = f"Project '{project_name}' {action}"

    node = MemoryNode(
        org_id=org_id,
        node_type="asana_project",
        title=f"Asana Project: {project_name[:50]}",
        text=text,
        meta_json={
            "project_gid": project_gid,
            "project_name": project_name,
            "action": action,
            "field_changed": field,
            "user_gid": user_gid,
            "user_name": user_name,
            "url": f"https://app.asana.com/0/{project_gid}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "asana_webhook.project",
        extra={
            "project_gid": project_gid,
            "action": action,
            "user": user_name,
        },
    )


async def _handle_story_event(
    event: dict,
    action: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle story (comment/activity) events."""
    resource = event.get("resource") or {}
    parent = event.get("parent") or {}
    user = event.get("user") or {}

    story_gid = resource.get("gid") or ""
    story_type = resource.get("resource_subtype") or "comment"

    parent_gid = parent.get("gid") or ""
    parent_type = parent.get("resource_type") or "task"
    parent_name = parent.get("name") or "Unknown"

    user_gid = user.get("gid") or ""
    user_name = user.get("name") or "Someone"

    # Story types: comment, system, add_assignee, remove_assignee, etc.
    if story_type == "comment_added" or story_type == "comment":
        text = f"{user_name} commented on {parent_type} '{parent_name}'"
    elif story_type == "added_to_project":
        text = f"{user_name} added {parent_type} '{parent_name}' to a project"
    elif story_type == "removed_from_project":
        text = f"{user_name} removed {parent_type} '{parent_name}' from a project"
    elif story_type == "assigned":
        text = f"{user_name} assigned {parent_type} '{parent_name}'"
    elif story_type == "unassigned":
        text = f"{user_name} unassigned {parent_type} '{parent_name}'"
    elif story_type == "marked_complete":
        text = f"{user_name} completed {parent_type} '{parent_name}'"
    elif story_type == "marked_incomplete":
        text = f"{user_name} reopened {parent_type} '{parent_name}'"
    else:
        text = f"{user_name} updated {parent_type} '{parent_name}' ({story_type})"

    node = MemoryNode(
        org_id=org_id,
        node_type="asana_story",
        title=f"Asana: {story_type} on {parent_name[:30]}",
        text=text,
        meta_json={
            "story_gid": story_gid,
            "story_type": story_type,
            "action": action,
            "parent_gid": parent_gid,
            "parent_type": parent_type,
            "parent_name": parent_name,
            "user_gid": user_gid,
            "user_name": user_name,
            "url": f"https://app.asana.com/0/0/{parent_gid}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "asana_webhook.story",
        extra={
            "story_gid": story_gid,
            "story_type": story_type,
            "parent_gid": parent_gid,
            "user": user_name,
        },
    )
