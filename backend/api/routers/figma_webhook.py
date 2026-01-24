"""
Figma webhook ingestion.

Handles Figma file update, comment, and library publish events.
Figma webhooks include a passcode in the payload for verification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/figma", tags=["figma_webhook"])
logger = logging.getLogger(__name__)


def verify_figma_passcode(
    payload: dict,
    expected_passcode: Optional[str],
) -> None:
    """
    Verify Figma webhook passcode.

    Figma includes the passcode in the webhook payload rather than headers.
    """
    if not expected_passcode:
        logger.warning("figma_webhook.no_passcode_configured")
        return

    passcode = payload.get("passcode")
    if not passcode:
        raise HTTPException(status_code=401, detail="Missing passcode in payload")

    if passcode != expected_passcode:
        raise HTTPException(status_code=401, detail="Invalid passcode")


@router.post("")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Figma webhooks.

    Figma webhook events:
    - FILE_UPDATE: File was modified
    - FILE_DELETE: File was deleted
    - FILE_VERSION_UPDATE: New version created
    - LIBRARY_PUBLISH: Library was published
    - FILE_COMMENT: Comment was added
    """
    payload = await request.json()
    verify_figma_passcode(payload, settings.figma_webhook_passcode)

    event_type = payload.get("event_type") or "unknown"
    org_id = x_org_id or settings.x_org_id

    try:
        if event_type == "FILE_UPDATE":
            await _handle_file_update(payload, org_id, db)

        elif event_type == "FILE_DELETE":
            await _handle_file_delete(payload, org_id, db)

        elif event_type == "FILE_VERSION_UPDATE":
            await _handle_file_version_update(payload, org_id, db)

        elif event_type == "LIBRARY_PUBLISH":
            await _handle_library_publish(payload, org_id, db)

        elif event_type == "FILE_COMMENT":
            await _handle_file_comment(payload, org_id, db)

        else:
            logger.info(
                "figma_webhook.unhandled_event",
                extra={"event": event_type},
            )

    except Exception as exc:
        logger.error(
            "figma_webhook.error",
            extra={"event": event_type, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_file_update(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle file update events."""
    file_key = payload.get("file_key") or ""
    file_name = payload.get("file_name") or "Untitled"
    timestamp = payload.get("timestamp") or ""

    # Triggered by info
    triggered_by = payload.get("triggered_by") or {}
    user_id = triggered_by.get("id") or ""
    user_handle = triggered_by.get("handle") or "unknown"

    # Webhook info
    webhook_id = payload.get("webhook_id") or ""

    node = MemoryNode(
        org_id=org_id,
        node_type="figma_file_update",
        title=f"Figma: {file_name} updated",
        text=f"{user_handle} updated the Figma file '{file_name}'",
        meta_json={
            "file_key": file_key,
            "file_name": file_name,
            "user_handle": user_handle,
            "user_id": user_id,
            "webhook_id": webhook_id,
            "timestamp": timestamp,
            "url": f"https://www.figma.com/file/{file_key}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "figma_webhook.file_update",
        extra={
            "file_key": file_key,
            "file_name": file_name,
            "user": user_handle,
        },
    )


async def _handle_file_delete(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle file delete events."""
    file_key = payload.get("file_key") or ""
    file_name = payload.get("file_name") or "Untitled"
    timestamp = payload.get("timestamp") or ""

    triggered_by = payload.get("triggered_by") or {}
    user_handle = triggered_by.get("handle") or "unknown"

    node = MemoryNode(
        org_id=org_id,
        node_type="figma_file_delete",
        title=f"Figma: {file_name} deleted",
        text=f"{user_handle} deleted the Figma file '{file_name}'",
        meta_json={
            "file_key": file_key,
            "file_name": file_name,
            "user_handle": user_handle,
            "timestamp": timestamp,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "figma_webhook.file_delete",
        extra={
            "file_key": file_key,
            "file_name": file_name,
            "user": user_handle,
        },
    )


async def _handle_file_version_update(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle file version update events."""
    file_key = payload.get("file_key") or ""
    file_name = payload.get("file_name") or "Untitled"
    timestamp = payload.get("timestamp") or ""

    triggered_by = payload.get("triggered_by") or {}
    user_handle = triggered_by.get("handle") or "unknown"

    # Version info
    version_id = payload.get("version_id") or ""
    label = payload.get("label") or ""
    description = payload.get("description") or ""

    node = MemoryNode(
        org_id=org_id,
        node_type="figma_version_update",
        title=f"Figma: {file_name} new version" + (f" - {label}" if label else ""),
        text=description or f"{user_handle} created a new version of '{file_name}'",
        meta_json={
            "file_key": file_key,
            "file_name": file_name,
            "version_id": version_id,
            "label": label,
            "description": description,
            "user_handle": user_handle,
            "timestamp": timestamp,
            "url": f"https://www.figma.com/file/{file_key}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "figma_webhook.version_update",
        extra={
            "file_key": file_key,
            "file_name": file_name,
            "version_id": version_id,
            "user": user_handle,
        },
    )


async def _handle_library_publish(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle library publish events."""
    file_key = payload.get("file_key") or ""
    file_name = payload.get("file_name") or "Untitled"
    timestamp = payload.get("timestamp") or ""

    triggered_by = payload.get("triggered_by") or {}
    user_handle = triggered_by.get("handle") or "unknown"

    # Library info
    description = payload.get("description") or ""

    # Created/modified/deleted components
    created_components = payload.get("created_components") or []
    modified_components = payload.get("modified_components") or []
    deleted_components = payload.get("deleted_components") or []

    # Created/modified/deleted styles
    created_styles = payload.get("created_styles") or []
    modified_styles = payload.get("modified_styles") or []
    deleted_styles = payload.get("deleted_styles") or []

    summary_parts = []
    if created_components:
        summary_parts.append(f"{len(created_components)} new components")
    if modified_components:
        summary_parts.append(f"{len(modified_components)} modified components")
    if deleted_components:
        summary_parts.append(f"{len(deleted_components)} deleted components")
    if created_styles:
        summary_parts.append(f"{len(created_styles)} new styles")
    if modified_styles:
        summary_parts.append(f"{len(modified_styles)} modified styles")
    if deleted_styles:
        summary_parts.append(f"{len(deleted_styles)} deleted styles")

    summary = ", ".join(summary_parts) if summary_parts else "No changes"

    node = MemoryNode(
        org_id=org_id,
        node_type="figma_library_publish",
        title=f"Figma Library: {file_name} published",
        text=f"{user_handle} published library '{file_name}': {summary}",
        meta_json={
            "file_key": file_key,
            "file_name": file_name,
            "description": description,
            "user_handle": user_handle,
            "timestamp": timestamp,
            "created_components": len(created_components),
            "modified_components": len(modified_components),
            "deleted_components": len(deleted_components),
            "created_styles": len(created_styles),
            "modified_styles": len(modified_styles),
            "deleted_styles": len(deleted_styles),
            "url": f"https://www.figma.com/file/{file_key}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "figma_webhook.library_publish",
        extra={
            "file_key": file_key,
            "file_name": file_name,
            "user": user_handle,
            "changes": summary,
        },
    )


async def _handle_file_comment(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle file comment events."""
    file_key = payload.get("file_key") or ""
    file_name = payload.get("file_name") or "Untitled"
    timestamp = payload.get("timestamp") or ""

    triggered_by = payload.get("triggered_by") or {}
    user_handle = triggered_by.get("handle") or "unknown"

    # Comment info
    comment = payload.get("comment") or {}
    comment_id = comment.get("id") or ""
    comment_text = comment.get("text") or ""
    parent_id = comment.get("parent_id")  # For replies

    # Mentions
    mentions = payload.get("mentions") or []
    mention_handles = [m.get("handle") for m in mentions if m.get("handle")]

    # Order ID for threaded comments
    order_id = payload.get("order_id")

    title = f"Figma Comment: {file_name}"
    if parent_id:
        title = f"Figma Reply: {file_name}"

    text = f"{user_handle}: {comment_text[:300]}"
    if mention_handles:
        text += f"\nMentions: {', '.join(mention_handles)}"

    node = MemoryNode(
        org_id=org_id,
        node_type="figma_comment",
        title=title,
        text=text,
        meta_json={
            "file_key": file_key,
            "file_name": file_name,
            "comment_id": comment_id,
            "comment_text": comment_text,
            "parent_id": parent_id,
            "user_handle": user_handle,
            "mentions": mention_handles,
            "order_id": order_id,
            "timestamp": timestamp,
            "url": f"https://www.figma.com/file/{file_key}",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "figma_webhook.comment",
        extra={
            "file_key": file_key,
            "comment_id": comment_id,
            "user": user_handle,
            "is_reply": parent_id is not None,
        },
    )
