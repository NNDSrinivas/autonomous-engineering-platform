"""
Microsoft Teams webhook ingestion (shared secret).

Note: Teams doesn't natively send signing headers in the same way as Slack.
We enforce a shared secret for now; upgrade to Graph change notifications with
signature verification when available.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import re

from backend.core.db import get_db
from backend.core.config import settings
from backend.core.webhooks import verify_shared_secret
from backend.core.auth_org import require_org
from backend.models.conversations import ConversationMessage, ConversationReply
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/teams", tags=["teams_webhook"])
logger = logging.getLogger(__name__)


@router.post("")
async def ingest(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    org_ctx: dict = Depends(require_org),
):
    """
    Ingest Teams messages for context hydration.
    """
    verify_shared_secret(
        x_webhook_secret, settings.teams_webhook_secret, connector="teams"
    )

    resource = payload.get("resourceData") or payload.get("value") or {}
    text = (
        resource.get("body", "")
        if isinstance(resource.get("body"), str)
        else resource.get("text", "")
    )
    channel = resource.get("channelId") or resource.get("channel")
    user = (
        resource.get("from", {}).get("user", {}).get("id")
        if isinstance(resource.get("from"), dict)
        else None
    )
    message_id = resource.get("id")
    thread_id = resource.get("replyToId")

    if not text:
        raise HTTPException(status_code=400, detail="Missing message text")

    if thread_id:
        parent = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.org_id == org_ctx["org_id"],
                ConversationMessage.platform == "teams",
                ConversationMessage.message_ts == thread_id,
            )
            .first()
        )
        if parent:
            reply = ConversationReply(
                org_id=org_ctx["org_id"],
                parent_id=parent.id,
                message_ts=message_id,
                user=user,
                text=text,
                meta_json=resource,
                created_at=datetime.now(timezone.utc),
            )
            db.add(reply)
    else:
        msg = ConversationMessage(
            org_id=org_ctx["org_id"],
            platform="teams",
            channel=channel,
            thread_ts=thread_id,
            message_ts=message_id,
            user=user,
            text=text,
            meta_json=resource,
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)

    db.commit()

    # Invalidate context packets for any Jira-style keys mentioned
    for match in re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", text):
        invalidate_context_packet_cache(match, org_ctx["org_id"])

    logger.info(
        "teams_webhook.event", extra={"org": org_ctx["org_id"], "channel": channel}
    )
    return {"status": "ok"}
