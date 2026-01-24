"""
Trello webhook ingestion.

Handles Trello board, list, and card events.
Trello webhooks include a signature in the request for verification.
"""

from __future__ import annotations

import hmac
import hashlib
import base64
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.config import settings
from backend.models.memory_graph import MemoryNode

router = APIRouter(prefix="/api/webhooks/trello", tags=["trello_webhook"])
logger = logging.getLogger(__name__)


def verify_trello_signature(
    signature: Optional[str],
    payload: bytes,
    callback_url: str,
    secret: Optional[str],
) -> None:
    """
    Verify Trello webhook signature.

    Trello uses base64(HMAC-SHA1(secret, body + callbackURL))
    """
    if not secret:
        logger.warning("trello_webhook.no_secret_configured")
        return

    if not signature:
        raise HTTPException(status_code=401, detail="Missing x-trello-webhook header")

    content = payload + callback_url.encode("utf-8")
    expected = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            content,
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.head("")
async def webhook_check():
    """
    Trello sends a HEAD request to verify the webhook URL.
    Must return 200 OK.
    """
    return {"status": "ok"}


@router.post("")
async def ingest(
    request: Request,
    x_trello_webhook: Optional[str] = Header(None, alias="x-trello-webhook"),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(None, alias="X-Org-Id"),
):
    """
    Ingest Trello webhooks.

    Trello webhook actions include:
    - createCard, updateCard, deleteCard
    - createList, updateList
    - createBoard, updateBoard
    - addMemberToCard, removeMemberFromCard
    - commentCard
    - addAttachmentToCard
    - updateCheckItemStateOnCard
    """
    body = await request.body()

    # Get callback URL for signature verification
    callback_url = str(request.url)
    verify_trello_signature(
        x_trello_webhook, body, callback_url, settings.trello_webhook_secret
    )

    payload = await request.json()

    action = payload.get("action") or {}
    action_type = action.get("type") or "unknown"
    org_id = x_org_id or settings.x_org_id

    try:
        # Card actions
        if action_type in [
            "createCard",
            "updateCard",
            "deleteCard",
            "copyCard",
            "moveCardToBoard",
        ]:
            await _handle_card_action(payload, action_type, org_id, db)

        # List actions
        elif action_type in [
            "createList",
            "updateList",
            "moveListFromBoard",
            "moveListToBoard",
        ]:
            await _handle_list_action(payload, action_type, org_id, db)

        # Board actions
        elif action_type in ["createBoard", "updateBoard", "deleteBoard"]:
            await _handle_board_action(payload, action_type, org_id, db)

        # Comment actions
        elif action_type in ["commentCard"]:
            await _handle_comment_action(payload, action_type, org_id, db)

        # Member actions
        elif action_type in [
            "addMemberToCard",
            "removeMemberFromCard",
            "addMemberToBoard",
            "removeMemberFromBoard",
        ]:
            await _handle_member_action(payload, action_type, org_id, db)

        # Checklist actions
        elif action_type in [
            "updateCheckItemStateOnCard",
            "addChecklistToCard",
            "createCheckItem",
        ]:
            await _handle_checklist_action(payload, action_type, org_id, db)

        # Attachment actions
        elif action_type in ["addAttachmentToCard", "deleteAttachmentFromCard"]:
            await _handle_attachment_action(payload, action_type, org_id, db)

        else:
            logger.info(
                "trello_webhook.unhandled_action",
                extra={"action_type": action_type},
            )

    except Exception as exc:
        logger.error(
            "trello_webhook.error",
            extra={"action_type": action_type, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Failed to process webhook")

    return {"status": "ok"}


async def _handle_card_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle card actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member = action.get("memberCreator") or {}

    card = data.get("card") or {}
    card_id = card.get("id") or ""
    card_name = card.get("name") or "Untitled"
    card_url = (
        f"https://trello.com/c/{card.get('shortLink', card_id)}"
        if card.get("shortLink")
        else ""
    )

    board = data.get("board") or {}
    board_name = board.get("name") or ""

    list_after = data.get("listAfter") or data.get("list") or {}
    list_before = data.get("listBefore") or {}
    list_name = list_after.get("name") or ""

    member_name = member.get("fullName") or member.get("username") or "Someone"

    # Build description based on action
    if action_type == "createCard":
        text = f"{member_name} created card '{card_name}' in '{list_name}'"
    elif action_type == "updateCard":
        if list_before.get("name") and list_after.get("name"):
            text = f"{member_name} moved '{card_name}' from '{list_before.get('name')}' to '{list_after.get('name')}'"
        else:
            old = data.get("old") or {}
            changes = list(old.keys())[:3]
            text = f"{member_name} updated card '{card_name}' ({', '.join(changes)})"
    elif action_type == "deleteCard":
        text = f"{member_name} deleted card '{card_name}'"
    elif action_type == "copyCard":
        text = f"{member_name} copied card '{card_name}'"
    elif action_type == "moveCardToBoard":
        text = f"{member_name} moved card '{card_name}' to board '{board_name}'"
    else:
        text = f"{member_name} {action_type} on card '{card_name}'"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_card",
        title=f"Trello: {card_name[:50]}",
        text=text,
        meta_json={
            "card_id": card_id,
            "card_name": card_name,
            "action_type": action_type,
            "board_name": board_name,
            "list_name": list_name,
            "member_name": member_name,
            "url": card_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()

    logger.info(
        "trello_webhook.card",
        extra={
            "card_id": card_id,
            "action_type": action_type,
            "member": member_name,
        },
    )


async def _handle_list_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle list actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member = action.get("memberCreator") or {}

    list_data = data.get("list") or {}
    list_id = list_data.get("id") or ""
    list_name = list_data.get("name") or "Untitled"

    board = data.get("board") or {}
    board_name = board.get("name") or ""

    member_name = member.get("fullName") or member.get("username") or "Someone"

    if action_type == "createList":
        text = f"{member_name} created list '{list_name}' on board '{board_name}'"
    elif action_type == "updateList":
        old = data.get("old") or {}
        if "name" in old:
            text = (
                f"{member_name} renamed list from '{old.get('name')}' to '{list_name}'"
            )
        else:
            text = f"{member_name} updated list '{list_name}'"
    else:
        text = f"{member_name} {action_type} list '{list_name}'"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_list",
        title=f"Trello List: {list_name[:50]}",
        text=text,
        meta_json={
            "list_id": list_id,
            "list_name": list_name,
            "action_type": action_type,
            "board_name": board_name,
            "member_name": member_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()


async def _handle_board_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle board actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member = action.get("memberCreator") or {}

    board = data.get("board") or {}
    board_id = board.get("id") or ""
    board_name = board.get("name") or "Untitled"
    board_url = (
        board.get("url") or f"https://trello.com/b/{board.get('shortLink', board_id)}"
    )

    member_name = member.get("fullName") or member.get("username") or "Someone"

    if action_type == "createBoard":
        text = f"{member_name} created board '{board_name}'"
    elif action_type == "updateBoard":
        text = f"{member_name} updated board '{board_name}'"
    elif action_type == "deleteBoard":
        text = f"{member_name} deleted board '{board_name}'"
    else:
        text = f"{member_name} {action_type} board '{board_name}'"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_board",
        title=f"Trello Board: {board_name[:50]}",
        text=text,
        meta_json={
            "board_id": board_id,
            "board_name": board_name,
            "action_type": action_type,
            "member_name": member_name,
            "url": board_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()


async def _handle_comment_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle comment actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member = action.get("memberCreator") or {}

    card = data.get("card") or {}
    card_name = card.get("name") or "Untitled"
    card_url = (
        f"https://trello.com/c/{card.get('shortLink')}" if card.get("shortLink") else ""
    )

    comment_text = data.get("text") or ""
    member_name = member.get("fullName") or member.get("username") or "Someone"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_comment",
        title=f"Trello Comment: {card_name[:30]}",
        text=f"{member_name} commented on '{card_name}': {comment_text[:200]}",
        meta_json={
            "card_name": card_name,
            "comment": comment_text,
            "member_name": member_name,
            "url": card_url,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()


async def _handle_member_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle member assignment actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member_creator = action.get("memberCreator") or {}

    card = data.get("card") or {}
    board = data.get("board") or {}
    target_member = data.get("member") or {}

    card_name = card.get("name") or ""
    board_name = board.get("name") or ""
    target_name = (
        target_member.get("name") or target_member.get("username") or "Someone"
    )
    member_name = (
        member_creator.get("fullName") or member_creator.get("username") or "Someone"
    )

    if action_type == "addMemberToCard":
        text = f"{member_name} assigned {target_name} to '{card_name}'"
    elif action_type == "removeMemberFromCard":
        text = f"{member_name} unassigned {target_name} from '{card_name}'"
    elif action_type == "addMemberToBoard":
        text = f"{member_name} added {target_name} to board '{board_name}'"
    elif action_type == "removeMemberFromBoard":
        text = f"{member_name} removed {target_name} from board '{board_name}'"
    else:
        text = f"{member_name} {action_type}"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_member",
        title=f"Trello: {action_type}",
        text=text,
        meta_json={
            "action_type": action_type,
            "card_name": card_name,
            "board_name": board_name,
            "target_member": target_name,
            "member_name": member_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()


async def _handle_checklist_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle checklist actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member = action.get("memberCreator") or {}

    card = data.get("card") or {}
    card_name = card.get("name") or ""
    checklist = data.get("checklist") or {}
    checklist_name = checklist.get("name") or ""
    check_item = data.get("checkItem") or {}
    check_item_name = check_item.get("name") or ""

    member_name = member.get("fullName") or member.get("username") or "Someone"

    if action_type == "updateCheckItemStateOnCard":
        state = check_item.get("state") or "complete"
        text = f"{member_name} marked '{check_item_name}' as {state} on '{card_name}'"
    elif action_type == "addChecklistToCard":
        text = f"{member_name} added checklist '{checklist_name}' to '{card_name}'"
    elif action_type == "createCheckItem":
        text = f"{member_name} added item '{check_item_name}' to '{card_name}'"
    else:
        text = f"{member_name} {action_type}"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_checklist",
        title=f"Trello Checklist: {card_name[:30]}",
        text=text,
        meta_json={
            "action_type": action_type,
            "card_name": card_name,
            "checklist_name": checklist_name,
            "check_item_name": check_item_name,
            "member_name": member_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()


async def _handle_attachment_action(
    payload: dict,
    action_type: str,
    org_id: Optional[str],
    db: Session,
) -> None:
    """Handle attachment actions."""
    action = payload.get("action") or {}
    data = action.get("data") or {}
    member = action.get("memberCreator") or {}

    card = data.get("card") or {}
    card_name = card.get("name") or ""
    attachment = data.get("attachment") or {}
    attachment_name = attachment.get("name") or ""

    member_name = member.get("fullName") or member.get("username") or "Someone"

    if action_type == "addAttachmentToCard":
        text = f"{member_name} attached '{attachment_name}' to '{card_name}'"
    elif action_type == "deleteAttachmentFromCard":
        text = f"{member_name} removed attachment from '{card_name}'"
    else:
        text = f"{member_name} {action_type}"

    node = MemoryNode(
        org_id=org_id,
        node_type="trello_attachment",
        title=f"Trello Attachment: {card_name[:30]}",
        text=text,
        meta_json={
            "action_type": action_type,
            "card_name": card_name,
            "attachment_name": attachment_name,
            "member_name": member_name,
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()
