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
from backend.integrations.teams_client import TeamsClient
from backend.services import connectors as connectors_service
from backend.models.conversations import ConversationMessage, ConversationReply
from backend.agent.context_packet import invalidate_context_packet_cache

router = APIRouter(prefix="/api/webhooks/teams", tags=["teams_webhook"])
logger = logging.getLogger(__name__)


@router.get("")
async def validate(validationToken: str | None = None):
    if validationToken:
        return validationToken
    return {"status": "ok"}


@router.post("")
async def ingest(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_webhook_secret: str | None = Header(None),
    x_org_id: str | None = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Teams messages for context hydration.
    """
    notifications = payload.get("value") or []
    notification = notifications[0] if notifications else payload

    client_state = notification.get("clientState") or payload.get("clientState")
    secret_candidate = x_webhook_secret or client_state
    verify_shared_secret(
        secret_candidate, settings.teams_webhook_secret, connector="teams"
    )

    org_id = x_org_id
    connector = None
    subscription_id = notification.get("subscriptionId")
    if not org_id and subscription_id:
        connector = connectors_service.find_connector_by_config(
            db, provider="teams", key="subscription_id", value=subscription_id
        )
        if connector:
            org_id = (connector.get("config") or {}).get("org_id")

    tenant_id = notification.get("tenantId") or payload.get("tenantId")
    if not org_id and tenant_id:
        connector = connectors_service.find_connector_by_config(
            db, provider="teams", key="tenant_id", value=tenant_id
        )
        if connector:
            org_id = (connector.get("config") or {}).get("org_id")

    if not org_id:
        raise HTTPException(status_code=404, detail="Org mapping not found for Teams")

    resource = notification.get("resourceData") or {}
    if not isinstance(resource, dict):
        resource = {}
    message_id = resource.get("id")
    channel = resource.get("channelId") or resource.get("channel")
    team_id = resource.get("teamId")
    thread_id = resource.get("replyToId")
    user = None
    if isinstance(resource.get("from"), dict):
        user = (resource.get("from") or {}).get("user", {}).get("id")

    text = ""
    if isinstance(resource.get("body"), dict):
        text = resource.get("body", {}).get("content") or ""
    elif isinstance(resource.get("body"), str):
        text = resource.get("body", "")
    if not text:
        text = resource.get("text") or ""

    resource_path = notification.get("resource")
    if isinstance(resource_path, str):
        parts = [p for p in resource_path.split("/") if p]
        if "teams" in parts and "channels" in parts and "messages" in parts:
            try:
                team_id = team_id or parts[parts.index("teams") + 1]
                channel = channel or parts[parts.index("channels") + 1]
                message_id = message_id or parts[parts.index("messages") + 1]
            except Exception:
                pass

    if not text and connector and message_id and team_id and channel:
        token = (connector.get("secrets") or {}).get("access_token") or (connector.get("secrets") or {}).get("token")
        if token:
            tc = TeamsClient(access_token=token, tenant_id=(connector.get("config") or {}).get("tenant_id"))
            msg = tc.get_channel_message(team_id, channel, message_id)
            body = msg.get("body", {}) or {}
            text = body.get("content") or msg.get("summary") or ""
            if not user and isinstance(msg.get("from"), dict):
                user = (msg.get("from") or {}).get("user", {}).get("id")

    if not text:
        raise HTTPException(status_code=400, detail="Missing message text")

    if thread_id:
        parent = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.org_id == org_id,
                ConversationMessage.platform == "teams",
                ConversationMessage.message_ts == thread_id,
            )
            .first()
        )
        if parent:
            reply = ConversationReply(
                org_id=org_id,
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
            org_id=org_id,
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
        invalidate_context_packet_cache(match, org_id)

    logger.info(
        "teams_webhook.event", extra={"org": org_id, "channel": channel}
    )
    return {"status": "ok"}
