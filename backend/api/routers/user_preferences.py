from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional

router = APIRouter(prefix="/api/user/preferences", tags=["user_preferences"])


def _current_user_id(user) -> str:
    return getattr(user, "user_id", None) or "default_user"


@router.get("")
def get_preferences(
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    row = (
        db.execute(
            text(
                """
                SELECT meta_json
                FROM navi_memory
                WHERE org_id = :org_id
                  AND user_id = :user_id
                  AND category = 'profile'
                  AND scope = 'preferences'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"org_id": org_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    return {"preferences": (row or {}).get("meta_json") or {}}


@router.post("")
def set_preferences(
    prefs: dict,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    if not isinstance(prefs, dict):
        raise HTTPException(status_code=400, detail="Preferences payload must be a JSON object")
    db.execute(
        text(
            """
            INSERT INTO navi_memory (org_id, user_id, category, scope, title, content, meta_json, importance, created_at, updated_at)
            VALUES (:org_id, :user_id, 'profile', 'preferences', 'user_preferences', 'User preferences', :prefs, 5, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"org_id": org_id, "user_id": user_id, "prefs": prefs},
    )
    db.commit()
    return {"preferences": prefs}
