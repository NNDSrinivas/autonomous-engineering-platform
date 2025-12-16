from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from backend.core.db import get_db
from backend.core.auth.deps import get_current_user_optional

router = APIRouter(prefix="/api/chat/sessions", tags=["chat_sessions"])

_SCHEMA_READY = False


def _ensure_schema(db: Session) -> None:
    """
    Ensure chat_session has archived, deleted_at, starred columns.
    Works on SQLite and Postgres by checking pragma / information_schema.
    """
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    try:
        # Detect existing columns
        existing = set()
        try:
            # SQLite pragma
            rows = db.execute(text("PRAGMA table_info(chat_session)")).fetchall()
            for r in rows:
                existing.add(str(r[1]))
        except Exception:
            # Postgres
            rows = db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='chat_session'"
                )
            ).fetchall()
            for r in rows:
                existing.add(str(r[0]))

        def add_column(sql: str):
            try:
                db.execute(text(sql))
                db.commit()
            except Exception:
                db.rollback()

        # Dialect-specific defaults/types
        dialect = getattr(getattr(db, "bind", None), "dialect", None)
        dialect_name = getattr(dialect, "name", "") if dialect else ""
        is_sqlite = dialect_name == "sqlite"

        if "archived" not in existing:
            add_column("ALTER TABLE chat_session ADD COLUMN archived TIMESTAMP")
        if "deleted_at" not in existing:
            add_column("ALTER TABLE chat_session ADD COLUMN deleted_at TIMESTAMP")
        if "starred" not in existing:
            if is_sqlite:
                add_column(
                    "ALTER TABLE chat_session ADD COLUMN starred INTEGER DEFAULT 0"
                )
            else:
                add_column(
                    "ALTER TABLE chat_session ADD COLUMN starred BOOLEAN DEFAULT FALSE"
                )
    finally:
        _SCHEMA_READY = True


def _current_user_id(user) -> str:
    return getattr(user, "user_id", None) or "default_user"


def _extract_org_context_for_sessions(user_id: str) -> list[str]:
    """Extract all possible org_id values to search for chat sessions."""
    org_ids = []

    # 1. Most common: VS Code extension default
    org_ids.append("org_vscode_extension")

    # 2. Workspace-based org_ids (multiple possible workspace paths)
    try:
        import hashlib

        workspace_path = "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform"
        workspace_hash = hashlib.md5(workspace_path.encode()).hexdigest()[:12]
        org_ids.append(f"org_workspace_{workspace_hash}")

        # Also try shorter hash (in case algorithm changed)
        workspace_hash_short = hashlib.md5(workspace_path.encode()).hexdigest()[:8]
        org_ids.append(f"org_workspace_{workspace_hash_short}")

        # Platform-based ID (aep = autonomous engineering platform)
        platform_hash = hashlib.md5(
            "autonomous-engineering-platform".encode()
        ).hexdigest()[:16]
        org_ids.append(f"org_aep_platform_{platform_hash}")
    except Exception:
        pass

    # 3. User-based org_id (both hashed and direct user_id)
    try:
        # Direct user_id format (what navi.py actually creates)
        org_ids.append(f"org_user_{user_id}")

        # Hashed format (legacy)
        import hashlib

        user_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
        org_ids.append(f"org_user_{user_hash}")
    except Exception:
        pass

    # 4. Legacy values found in database
    org_ids.extend(["dev_org", None])  # None for very old records

    return org_ids


@router.get("")
def list_sessions(
    user_id: str | None = None,  # Allow explicit user_id parameter
    include_archived: bool = False,
    include_deleted: bool = False,
    include_starred: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    actual_user_id = user_id or _current_user_id(user)

    rows = (
        db.execute(
            text(
                """
                SELECT cs.id, cs.title, cs.created_at, cs.updated_at, cs.archived, cs.deleted_at, cs.starred,
                       (SELECT message FROM chat_history ch WHERE ch.session_id = cs.id ORDER BY ch.created_at DESC LIMIT 1) as last_message,
                       (SELECT role FROM chat_history ch WHERE ch.session_id = cs.id ORDER BY ch.created_at DESC LIMIT 1) as last_role,
                       cs.user_id
                FROM chat_session cs
                WHERE cs.user_id = :user_id
                  AND (:include_archived OR cs.archived IS NULL)
                  AND (:include_deleted OR cs.deleted_at IS NULL)
                  AND (:include_starred OR cs.starred IS NULL OR cs.starred = TRUE)
                ORDER BY cs.updated_at DESC
                """
            ),
            {
                "user_id": actual_user_id,
                "include_archived": include_archived,
                "include_deleted": include_deleted,
                "include_starred": include_starred,
            },
        )
        .mappings()
        .all()
    )

    return {"items": [dict(r) for r in rows]}


@router.post("")
def create_session(
    title: str = "",
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    # Use default org_id for VS Code extension compatibility
    org_id = "org_vscode_extension"
    user_id = _current_user_id(user)
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    dialect_name = getattr(dialect, "name", "") if dialect else ""
    now_sql = "CURRENT_TIMESTAMP" if dialect_name == "sqlite" else "NOW()"
    result = db.execute(
        text(
            f"""
            INSERT INTO chat_session (org_id, user_id, title, created_at, updated_at)
            VALUES (:org_id, :user_id, :title, {now_sql}, {now_sql})
            RETURNING id, title, created_at, updated_at
            """
        ),
        {"org_id": org_id, "user_id": user_id, "title": title or "New session"},
    )
    db.commit()
    row = result.mappings().first()
    return dict(row)


@router.delete("/{session_id}")
def delete_session(
    session_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    # Use default org_id for VS Code extension compatibility
    user_id = user_id or _current_user_id(user)
    # Soft delete: mark deleted_at; retain for up to 30 days
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    dialect_name = getattr(dialect, "name", "") if dialect else ""
    now_sql = "CURRENT_TIMESTAMP" if dialect_name == "sqlite" else "NOW()"
    db.execute(
        text(
            f"UPDATE chat_session SET deleted_at = {now_sql} WHERE id = :sid AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": user_id},
    )
    db.commit()
    return {"deleted": True, "soft": True}


@router.post("/{session_id}/archive")
def archive_session(
    session_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    user_id = user_id or _current_user_id(user)
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    dialect_name = getattr(dialect, "name", "") if dialect else ""
    now_sql = "CURRENT_TIMESTAMP" if dialect_name == "sqlite" else "NOW()"
    db.execute(
        text(
            f"UPDATE chat_session SET archived = {now_sql} WHERE id = :sid AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": user_id},
    )
    db.commit()
    return {"archived": True}


@router.post("/{session_id}/unarchive")
def unarchive_session(
    session_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    user_id = user_id or _current_user_id(user)
    db.execute(
        text(
            "UPDATE chat_session SET archived = NULL WHERE id = :sid AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": user_id},
    )
    db.commit()
    return {"archived": False}


@router.post("/{session_id}/restore")
def restore_session(
    session_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Restore a soft-deleted session within a 30-day retention window.
    """
    _ensure_schema(db)
    user_id = user_id or _current_user_id(user)

    # Only allow restore within 30 days
    row = (
        db.execute(
            text(
                """
            SELECT deleted_at FROM chat_session
            WHERE id = :sid AND user_id = :user_id
            """
            ),
            {"sid": session_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )

    if not row or not row.get("deleted_at"):
        raise HTTPException(status_code=404, detail="Session not found or not deleted")

    deleted_at = row["deleted_at"]
    from datetime import timezone, timedelta

    if deleted_at < datetime.now(timezone.utc) - timedelta(days=30):
        raise HTTPException(status_code=410, detail="Restore window expired (>30 days)")

    db.execute(
        text(
            "UPDATE chat_session SET deleted_at = NULL WHERE id = :sid AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": user_id},
    )
    db.commit()
    return {"restored": True}


@router.post("/{session_id}/star")
def star_session(
    session_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    user_id = user_id or _current_user_id(user)
    db.execute(
        text(
            "UPDATE chat_session SET starred = TRUE WHERE id = :sid AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": user_id},
    )
    db.commit()
    return {"starred": True}


@router.post("/{session_id}/unstar")
def unstar_session(
    session_id: int,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
):
    _ensure_schema(db)
    user_id = user_id or _current_user_id(user)
    db.execute(
        text(
            "UPDATE chat_session SET starred = FALSE WHERE id = :sid AND user_id = :user_id"
        ),
        {"sid": session_id, "user_id": user_id},
    )
    db.commit()
    return {"starred": False}
