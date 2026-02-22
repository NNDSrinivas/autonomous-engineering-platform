from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional
import uuid

from backend.core.db import get_db
from backend.core.auth.deps import get_current_user_optional

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_sessions"])


def _current_user_id(user) -> str:
    return getattr(user, "user_id", None) or "default_user"


def _get_or_create_user(db: Session, auth0_sub: str, email: Optional[str] = None, display_name: Optional[str] = None) -> int:
    """
    Get or create user from Auth0 sub (maps to users.sub column).
    Returns integer user_id for use with navi_conversations.
    """
    # Check if user exists
    result = db.execute(
        text("SELECT id, org_id FROM users WHERE sub = :sub"),
        {"sub": auth0_sub}
    ).mappings().first()

    if result:
        return result["id"]

    # User doesn't exist, need to create
    # First ensure default org exists
    org_result = db.execute(
        text("SELECT id FROM organizations WHERE org_key = :org_key"),
        {"org_key": "default"}
    ).mappings().first()

    if org_result:
        org_id = org_result["id"]
    else:
        # Create default org
        org_create = db.execute(
            text("""
                INSERT INTO organizations (org_key, name)
                VALUES (:org_key, :name)
                RETURNING id
            """),
            {"org_key": "default", "name": "Default Organization"}
        ).mappings().first()
        org_id = org_create["id"]
        db.commit()

    # Create user
    user_email = email or f"{auth0_sub.replace('|', '-')}@navralabs.com"
    user_name = display_name or auth0_sub.split("|")[-1]

    user_result = db.execute(
        text("""
            INSERT INTO users (sub, email, display_name, org_id)
            VALUES (:sub, :email, :display_name, :org_id)
            RETURNING id
        """),
        {
            "sub": auth0_sub,
            "email": user_email,
            "display_name": user_name,
            "org_id": org_id
        }
    ).mappings().first()

    db.commit()
    return user_result["id"]


@router.get("")
def list_sessions(
    user_id: str | None = None,  # Allow explicit user_id parameter (Auth0 sub)
    include_archived: bool = False,
    include_deleted: bool = False,
    include_starred: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    List chat sessions from navi_conversations table (shared with VSCode extension).
    This provides unified chat history across web and VSCode.
    """
    auth0_sub = user_id or _current_user_id(user)

    # Get or create user (maps Auth0 sub to integer user_id)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    # Query navi_conversations with status filtering
    # status can be: 'active', 'completed', 'archived'
    status_filter = []
    if not include_archived:
        status_filter.append("nc.status != 'archived'")
    if not include_deleted:
        # Assuming 'deleted' status or we could add deleted_at column
        status_filter.append("nc.status != 'deleted'")

    status_where = " AND " + " AND ".join(status_filter) if status_filter else ""

    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    nc.id,
                    nc.title,
                    nc.created_at,
                    nc.updated_at,
                    nc.status,
                    nc.is_pinned,
                    nc.is_starred,
                    nc.workspace_path,
                    (SELECT content FROM navi_messages nm
                     WHERE nm.conversation_id = nc.id
                     ORDER BY nm.created_at DESC LIMIT 1) as last_message,
                    (SELECT role FROM navi_messages nm
                     WHERE nm.conversation_id = nc.id
                     ORDER BY nm.created_at DESC LIMIT 1) as last_role,
                    (SELECT COUNT(*) FROM navi_messages nm
                     WHERE nm.conversation_id = nc.id) as message_count
                FROM navi_conversations nc
                WHERE nc.user_id = :user_id {status_where}
                ORDER BY nc.updated_at DESC
                """
            ),
            {"user_id": internal_user_id},
        )
        .mappings()
        .all()
    )

    return {"items": [dict(r) for r in rows]}


@router.post("")
def create_session(
    title: str = "",
    workspace_path: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Create new chat session in navi_conversations (shared with VSCode extension).
    Returns UUID-based conversation ID.
    """
    auth0_sub = _current_user_id(user)

    # Get or create user (returns integer user_id and org_id)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    # Get user's org_id
    org_result = db.execute(
        text("SELECT org_id FROM users WHERE id = :user_id"),
        {"user_id": internal_user_id}
    ).mappings().first()

    org_id = org_result["org_id"]

    # Create conversation in navi_conversations table
    result = db.execute(
        text(
            """
            INSERT INTO navi_conversations
            (id, user_id, org_id, title, workspace_path, status, is_pinned, is_starred, created_at, updated_at)
            VALUES (gen_random_uuid(), :user_id, :org_id, :title, :workspace_path, 'active', false, false, NOW(), NOW())
            RETURNING id, title, created_at, updated_at, status, workspace_path
            """
        ),
        {
            "user_id": internal_user_id,
            "org_id": org_id,
            "title": title or "New Chat",
            "workspace_path": workspace_path
        },
    )
    db.commit()
    row = result.mappings().first()
    return dict(row)


@router.delete("/{session_id}")
def delete_session(
    session_id: str,  # UUID string
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Soft delete conversation by setting status to 'deleted'.
    Uses navi_conversations table.
    """
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    # Soft delete: change status to 'deleted'
    db.execute(
        text(
            "UPDATE navi_conversations SET status = 'deleted', updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"deleted": True, "soft": True}


@router.post("/{session_id}/archive")
def archive_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """Archive conversation by setting status to 'archived'."""
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    db.execute(
        text(
            "UPDATE navi_conversations SET status = 'archived', updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"archived": True}


@router.post("/{session_id}/unarchive")
def unarchive_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """Unarchive conversation by setting status back to 'active'."""
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    db.execute(
        text(
            "UPDATE navi_conversations SET status = 'active', updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"archived": False}


@router.post("/{session_id}/restore")
def restore_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Restore a soft-deleted conversation by setting status back to 'active'.
    """
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    # Check if conversation exists and is deleted
    row = (
        db.execute(
            text(
                """
            SELECT status, updated_at FROM navi_conversations
            WHERE id = CAST(:sid AS uuid) AND user_id = :user_id
            """
            ),
            {"sid": session_id, "user_id": internal_user_id},
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    if row["status"] != "deleted":
        raise HTTPException(status_code=400, detail="Session is not deleted")

    db.execute(
        text(
            "UPDATE navi_conversations SET status = 'active', updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"restored": True}


@router.post("/{session_id}/star")
def star_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """Star conversation (set is_starred = true)."""
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    db.execute(
        text(
            "UPDATE navi_conversations SET is_starred = TRUE, updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"starred": True}


@router.post("/{session_id}/unstar")
def unstar_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """Unstar conversation (set is_starred = false)."""
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    db.execute(
        text(
            "UPDATE navi_conversations SET is_starred = FALSE, updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"starred": False}


@router.post("/{session_id}/pin")
def pin_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """Pin conversation (set is_pinned = true)."""
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    db.execute(
        text(
            "UPDATE navi_conversations SET is_pinned = TRUE, updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"pinned": True}


@router.post("/{session_id}/unpin")
def unpin_session(
    session_id: str,  # UUID
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """Unpin conversation (set is_pinned = false)."""
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    db.execute(
        text(
            "UPDATE navi_conversations SET is_pinned = FALSE, updated_at = NOW() WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    )
    db.commit()
    return {"pinned": False}


@router.get("/{session_id}/messages")
def get_messages(
    session_id: str,  # UUID
    user_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Get messages for a conversation.
    Returns messages from navi_messages table.
    """
    auth0_sub = user_id or _current_user_id(user)
    internal_user_id = _get_or_create_user(db, auth0_sub)

    # Verify user owns this conversation
    conversation = db.execute(
        text(
            "SELECT id FROM navi_conversations WHERE id = CAST(:sid AS uuid) AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": internal_user_id},
    ).mappings().first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    rows = (
        db.execute(
            text(
                """
                SELECT
                    id,
                    role,
                    content,
                    created_at,
                    message_metadata
                FROM navi_messages
                WHERE conversation_id = CAST(:sid AS uuid)
                ORDER BY created_at ASC
                LIMIT :limit
                """
            ),
            {"sid": session_id, "limit": limit},
        )
        .mappings()
        .all()
    )

    return {"items": [dict(r) for r in rows]}
