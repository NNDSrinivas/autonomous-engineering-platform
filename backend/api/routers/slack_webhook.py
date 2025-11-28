"""
Slack/Teams webhook ingestion with shared-secret verification.

Note: This uses a shared secret header for now; upgrade to signature verification
with timestamps as we wire the official Slack signing secret flow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.core.webhooks import verify_slack_signature
from backend.core.auth_org import require_org
import re
from backend.models.memory_graph import MemoryNode
from backend.models.conversations import ConversationMessage, ConversationReply
from datetime import datetime
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/slack", tags=["slack_webhook"])
logger = logging.getLogger(__name__)


@router.post("")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    x_slack_request_timestamp: str | None = Header(None, alias="X-Slack-Request-Timestamp"),
    x_slack_signature: str | None = Header(None, alias="X-Slack-Signature"),
    org_ctx: dict = Depends(require_org),
):
    """
    Ingest Slack/Teams events (messages, threads) for context hydration.
    """
    body = await request.body()
    verify_slack_signature(
        timestamp=x_slack_request_timestamp,
        signature=x_slack_signature,
        payload=body,
        signing_secret=settings.slack_signing_secret,
    )

    payload: Dict[str, Any] = await request.json()

    # Slack URL verification challenge
    if payload.get("type") == "url_verification" and payload.get("challenge"):
        return {"challenge": payload["challenge"]}

    event = payload.get("event") or {}
    event_type = event.get("type")
    if not event_type:
        raise HTTPException(status_code=400, detail="Missing event type")

    # Persist message/threads into memory graph for retrieval
    if event_type in ("message", "app_mention"):
        text = event.get("text", "")
        channel = event.get("channel")
        user = event.get("user")
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")

        if thread_ts and thread_ts != ts:
            # Treat as a reply
            parent = (
                db.query(ConversationMessage)
                .filter(
                    ConversationMessage.org_id == org_ctx["org_id"],
                    ConversationMessage.platform == "slack",
                    ConversationMessage.channel == channel,
                    ConversationMessage.message_ts == thread_ts,
                )
                .first()
            )
            if parent:
                reply = ConversationReply(
                    org_id=org_ctx["org_id"],
                    parent_id=parent.id,
                    message_ts=ts,
                    user=user,
                    text=text,
                    meta_json=event,
                    created_at=datetime.utcnow(),
                )
                db.add(reply)
        else:
            msg = ConversationMessage(
                org_id=org_ctx["org_id"],
                platform="slack",
                channel=channel,
                thread_ts=thread_ts,
                message_ts=ts,
                user=user,
                text=text,
                meta_json=event,
                created_at=datetime.utcnow(),
            )
            db.add(msg)

        node = MemoryNode(
            org_id=org_ctx["org_id"],
            node_type="slack_msg",
            title=f"{channel}#{ts}",
            text=text,
            meta_json={
                "channel": channel,
                "user": user,
                "ts": ts,
                "thread_ts": thread_ts,
                "event": event_type,
            },
            created_at=datetime.utcnow(),
        )
        db.add(node)
        db.commit()

    logger.info(
        "slack_webhook.event",
        extra={"event_type": event_type, "org": org_ctx["org_id"], "channel": event.get("channel")},
    )

    # Invalidate context packets for any Jira-style keys mentioned
    for match in re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", payload.get("event", {}).get("text", "")):
        invalidate_context_packet_cache(match, org_ctx["org_id"])

    return {"status": "ok"}
