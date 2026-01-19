"""
Discord webhook/event ingestion.

Handles Discord gateway events for message and member tracking.
Note: Discord doesn't use traditional webhooks - events come via Gateway.
This router handles HTTP callbacks from Discord Interactions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/discord", tags=["discord_webhook"])
logger = logging.getLogger(__name__)


def verify_discord_signature(
    signature: Optional[str],
    timestamp: Optional[str],
    body: bytes,
    public_key: Optional[str],
) -> None:
    """
    Verify Discord interaction signature using Ed25519.

    Discord uses Ed25519 signatures for webhook verification.
    """
    if not public_key:
        logger.warning("discord_webhook.no_public_key_configured")
        return

    if not signature or not timestamp:
        raise HTTPException(
            status_code=401,
            detail="Missing signature or timestamp headers",
        )

    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        message = timestamp.encode() + body
        verify_key.verify(message, bytes.fromhex(signature))
    except BadSignatureError:
        raise HTTPException(status_code=401, detail="Invalid signature")
    except Exception as exc:
        logger.error("discord_webhook.signature_error", error=str(exc))
        raise HTTPException(status_code=401, detail="Signature verification failed")


@router.post("")
async def ingest(
    request: Request,
    x_signature_ed25519: Optional[str] = Header(None, alias="X-Signature-Ed25519"),
    x_signature_timestamp: Optional[str] = Header(None, alias="X-Signature-Timestamp"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Handle Discord Interactions webhook.

    Discord sends interactions (slash commands, buttons, etc.) to this endpoint.
    Must respond with appropriate interaction response.

    For message events, use a Discord bot with Gateway connection instead.
    """
    body = await request.body()
    verify_discord_signature(
        x_signature_ed25519,
        x_signature_timestamp,
        body,
        settings.discord_public_key,
    )

    payload = await request.json()
    interaction_type = payload.get("type")
    org_id = x_org_id or settings.x_org_id

    # Type 1 = PING (verification)
    if interaction_type == 1:
        return {"type": 1}  # PONG

    # Type 2 = APPLICATION_COMMAND
    # Type 3 = MESSAGE_COMPONENT
    # Type 4 = APPLICATION_COMMAND_AUTOCOMPLETE
    # Type 5 = MODAL_SUBMIT

    try:
        if interaction_type == 2:  # Application Command
            await _handle_application_command(payload, org_id, db)
        elif interaction_type == 3:  # Message Component
            await _handle_message_component(payload, org_id, db)
        elif interaction_type == 5:  # Modal Submit
            await _handle_modal_submit(payload, org_id, db)
        else:
            logger.info(
                "discord_webhook.unhandled_type",
                extra={"type": interaction_type},
            )

    except Exception as exc:
        logger.error(
            "discord_webhook.error",
            extra={"type": interaction_type, "error": str(exc)},
        )

    # Return acknowledgment (type 4 = DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE)
    return {
        "type": 4,
        "data": {
            "content": "Processing...",
            "flags": 64,  # Ephemeral
        },
    }


async def _handle_application_command(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle slash command interactions."""
    data = payload.get("data") or {}
    command_name = data.get("name") or "unknown"

    user = payload.get("user") or payload.get("member", {}).get("user") or {}
    user_name = user.get("username") or "unknown"

    guild_id = payload.get("guild_id")
    channel_id = payload.get("channel_id")

    # Extract options
    options = data.get("options") or []
    options_text = ", ".join(
        f"{opt.get('name')}={opt.get('value')}"
        for opt in options
    )

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_command",
        title=f"Discord Command: /{command_name}",
        text=f"User {user_name} ran /{command_name}" + (f" with {options_text}" if options_text else ""),
        meta_json={
            "command": command_name,
            "user": user_name,
            "user_id": user.get("id"),
            "guild_id": guild_id,
            "channel_id": channel_id,
            "options": {opt.get("name"): opt.get("value") for opt in options},
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.command",
        extra={
            "command": command_name,
            "user": user_name,
            "guild_id": guild_id,
        },
    )


async def _handle_message_component(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle button/select menu interactions."""
    data = payload.get("data") or {}
    custom_id = data.get("custom_id") or "unknown"
    component_type = data.get("component_type") or 0

    user = payload.get("user") or payload.get("member", {}).get("user") or {}
    user_name = user.get("username") or "unknown"

    guild_id = payload.get("guild_id")
    channel_id = payload.get("channel_id")

    # Get values for select menus
    values = data.get("values") or []

    component_types = {
        2: "button",
        3: "string_select",
        5: "user_select",
        6: "role_select",
        7: "mentionable_select",
        8: "channel_select",
    }
    type_name = component_types.get(component_type, "unknown")

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_interaction",
        title=f"Discord {type_name}: {custom_id}",
        text=f"User {user_name} interacted with {type_name}" + (f": {values}" if values else ""),
        meta_json={
            "custom_id": custom_id,
            "component_type": type_name,
            "user": user_name,
            "user_id": user.get("id"),
            "guild_id": guild_id,
            "channel_id": channel_id,
            "values": values,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.component",
        extra={
            "custom_id": custom_id,
            "type": type_name,
            "user": user_name,
        },
    )


async def _handle_modal_submit(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle modal form submissions."""
    data = payload.get("data") or {}
    custom_id = data.get("custom_id") or "unknown"

    user = payload.get("user") or payload.get("member", {}).get("user") or {}
    user_name = user.get("username") or "unknown"

    guild_id = payload.get("guild_id")
    channel_id = payload.get("channel_id")

    # Extract form values
    components = data.get("components") or []
    form_values = {}
    for row in components:
        for component in row.get("components", []):
            field_id = component.get("custom_id")
            value = component.get("value")
            if field_id:
                form_values[field_id] = value

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_modal",
        title=f"Discord Modal: {custom_id}",
        text=f"User {user_name} submitted modal {custom_id}",
        meta_json={
            "custom_id": custom_id,
            "user": user_name,
            "user_id": user.get("id"),
            "guild_id": guild_id,
            "channel_id": channel_id,
            "form_values": form_values,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.modal",
        extra={
            "custom_id": custom_id,
            "user": user_name,
            "fields": list(form_values.keys()),
        },
    )


# =============================================================================
# Message Ingestion Endpoint (for bot-forwarded messages)
# =============================================================================


@router.post("/messages")
async def ingest_message(
    request: Request,
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
    x_bot_token: Optional[str] = Header(None, alias="X-Bot-Token"),
):
    """
    Ingest Discord messages forwarded by a bot.

    Since Discord doesn't have traditional message webhooks,
    a bot must forward messages to this endpoint.
    """
    # Verify bot token
    if x_bot_token != settings.discord_bot_token:
        raise HTTPException(status_code=401, detail="Invalid bot token")

    payload = await request.json()
    org_id = x_org_id or settings.x_org_id

    event_type = payload.get("event_type") or "MESSAGE_CREATE"

    try:
        if event_type == "MESSAGE_CREATE":
            await _handle_message_create(payload, org_id, db)
        elif event_type == "MESSAGE_UPDATE":
            await _handle_message_update(payload, org_id, db)
        elif event_type == "GUILD_MEMBER_ADD":
            await _handle_member_join(payload, org_id, db)
        elif event_type == "GUILD_MEMBER_REMOVE":
            await _handle_member_leave(payload, org_id, db)
        else:
            logger.info(
                "discord_webhook.unhandled_event",
                extra={"event": event_type},
            )

    except Exception as exc:
        logger.error(
            "discord_webhook.message_error",
            extra={"event": event_type, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process event")

    return {"status": "ok"}


async def _handle_message_create(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle new message events."""
    message = payload.get("message") or payload
    message_id = message.get("id")
    content = message.get("content") or ""
    channel_id = message.get("channel_id")
    guild_id = message.get("guild_id")

    author = message.get("author") or {}
    author_name = author.get("username") or "unknown"
    author_id = author.get("id")

    # Skip bot messages unless specified
    if author.get("bot") and not payload.get("include_bots"):
        return

    # Get channel info if provided
    channel_name = payload.get("channel_name") or ""
    guild_name = payload.get("guild_name") or ""

    # Extract attachments
    attachments = message.get("attachments") or []
    attachment_names = [a.get("filename") for a in attachments]

    # Extract embeds summary
    embeds = message.get("embeds") or []
    embed_titles = [e.get("title") for e in embeds if e.get("title")]

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_message",
        title=f"Discord: {author_name} in #{channel_name or channel_id}",
        text=content[:2000] if content else "[No text content]",
        meta_json={
            "message_id": message_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "author": author_name,
            "author_id": author_id,
            "attachments": attachment_names,
            "embed_titles": embed_titles,
            "timestamp": message.get("timestamp"),
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.message_create",
        extra={
            "message_id": message_id,
            "channel": channel_name or channel_id,
            "author": author_name,
        },
    )


async def _handle_message_update(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle message edit events."""
    message = payload.get("message") or payload
    message_id = message.get("id")
    content = message.get("content") or ""
    channel_id = message.get("channel_id")

    author = message.get("author") or {}
    author_name = author.get("username") or "unknown"

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_message_edit",
        title=f"Discord Edit: {author_name} in #{channel_id}",
        text=f"[Edited] {content[:1500]}" if content else "[Message edited]",
        meta_json={
            "message_id": message_id,
            "channel_id": channel_id,
            "author": author_name,
            "edited_timestamp": message.get("edited_timestamp"),
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.message_update",
        extra={"message_id": message_id, "author": author_name},
    )


async def _handle_member_join(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle member join events."""
    member = payload.get("member") or payload
    user = member.get("user") or {}
    user_name = user.get("username") or "unknown"
    user_id = user.get("id")
    guild_id = payload.get("guild_id")
    guild_name = payload.get("guild_name") or ""

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_member_join",
        title=f"Discord: {user_name} joined {guild_name or guild_id}",
        text=f"User {user_name} joined the server",
        meta_json={
            "user": user_name,
            "user_id": user_id,
            "guild_id": guild_id,
            "guild_name": guild_name,
            "joined_at": member.get("joined_at"),
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.member_join",
        extra={"user": user_name, "guild_id": guild_id},
    )


async def _handle_member_leave(
    payload: dict,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle member leave events."""
    user = payload.get("user") or {}
    user_name = user.get("username") or "unknown"
    user_id = user.get("id")
    guild_id = payload.get("guild_id")
    guild_name = payload.get("guild_name") or ""

    node = MemoryNode(
        org_id=org_id,
        node_type="discord_member_leave",
        title=f"Discord: {user_name} left {guild_name or guild_id}",
        text=f"User {user_name} left the server",
        meta_json={
            "user": user_name,
            "user_id": user_id,
            "guild_id": guild_id,
            "guild_name": guild_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "discord_webhook.member_leave",
        extra={"user": user_name, "guild_id": guild_id},
    )
