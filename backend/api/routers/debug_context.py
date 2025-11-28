from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional
from backend.core.settings import settings

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/context")
def debug_context(
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = getattr(user, "user_id", None) if user else None

    jira_count = db.execute(
        text(
            "SELECT COUNT(*) FROM jira_issue ji JOIN jira_connection jc ON jc.id = ji.connection_id WHERE (:org_id IS NULL OR jc.org_id = :org_id)"
        ),
        {"org_id": org_id},
    ).scalar_one()

    return {
        "jwt_enabled": settings.JWT_ENABLED,
        "user_id": user_id,
        "org_id": org_id,
        "jira_issues": jira_count,
    }
