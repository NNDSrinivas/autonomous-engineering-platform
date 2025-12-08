"""
Lightweight debug endpoint to inspect auth/org context and data availability.

Use only in trusted environments. Returns user/org derived from auth plus basic
ingestion counts to help diagnose empty Jira lists or missing context.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.core.settings import settings
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional

router = APIRouter(prefix="/api/debug", tags=["debug"])
logger = logging.getLogger(__name__)


@router.get("/context")
def debug_context(
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Return current user/org and basic ingestion counts for diagnostics.
    """
    org_id = org_ctx.get("org_id")
    user_id = getattr(user, "user_id", None) if user else None

    jira_count = db.execute(
        text(
            "SELECT COUNT(*) FROM jira_issue ji JOIN jira_connection jc ON jc.id = ji.connection_id WHERE jc.org_id = :org"
        ),
        {"org": org_id},
    ).scalar_one()

    gh_count = db.execute(
        text(
            "SELECT COUNT(*) FROM gh_issue_pr gip JOIN gh_repo gr ON gr.id = gip.repo_id JOIN gh_connection gc ON gc.id = gr.connection_id WHERE gc.org_id = :org"
        ),
        {"org": org_id},
    ).scalar_one()

    return {
        "jwt_enabled": settings.JWT_ENABLED,
        "user_id": user_id,
        "org_id": org_id,
        "jira_issues": jira_count,
        "github_items": gh_count,
    }
