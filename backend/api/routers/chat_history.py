from __future__ import annotations


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional

router = APIRouter(prefix="/api/chat", tags=["chat_history"])


def _current_user_id(user) -> str:
    return getattr(user, "user_id", None) or "default_user"


@router.get("/history")
def list_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    rows = (
        db.execute(
            text(
                """
                SELECT id, role, message, created_at
                FROM chat_history
                WHERE org_id = :org_id AND user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"org_id": org_id, "user_id": user_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return {"items": [dict(r) for r in rows]}


@router.delete("/history")
def clear_history(
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    db.execute(
        text(
            "DELETE FROM chat_history WHERE org_id = :org_id AND user_id = :user_id"
        ),
        {"org_id": org_id, "user_id": user_id},
    )
    db.commit()
    return {"cleared": True}
