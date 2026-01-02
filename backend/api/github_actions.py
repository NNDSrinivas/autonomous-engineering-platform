"""
GitHub actions API: create draft PRs and fetch PR status.
"""

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging
import os

from backend.core.db import get_db
from backend.services.github_write import GitHubWriteService

router = APIRouter(prefix="/api/github", tags=["github-actions"])
logger = logging.getLogger(__name__)


class CreatePROptions(BaseModel):
    repo_full_name: str = Field(..., description="owner/repo")
    base: str = Field(..., description="Base branch")
    head: str = Field(..., description="Head branch")
    title: str = Field(..., description="PR title")
    body: str = Field("", description="PR body/description")
    ticket_key: Optional[str] = Field(None, description="Optional ticket key to link")
    dry_run: bool = Field(False, description="If true, do not create PR (preview only)")
    connector_name: Optional[str] = Field(None, description="Connector name (default)")


class PRStatusRequest(BaseModel):
    repo_full_name: str
    pr_number: int
    connector_name: Optional[str] = None


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_TOKEN (or GH_TOKEN) is required for GitHub actions",
        )
    return token


@router.post("/pr/create")
async def create_pr(req: CreatePROptions, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Create a draft PR (or preview payload if dry_run=True).
    """
    try:
        token = _get_token()
        if req.connector_name:
            from backend.services.connectors import get_connector

            conn = get_connector(
                db, user_id="default_user", provider="github", name=req.connector_name
            )
            if conn:
                token = conn.get("secrets", {}).get("token") or conn.get("secrets", {}).get("access_token") or token
        svc = GitHubWriteService(token=token)
        result = await svc.draft_pr(
          repo_full_name=req.repo_full_name,
          base=req.base,
          head=req.head,
          title=req.title,
          body=req.body,
          ticket_key=req.ticket_key,
          dry_run=req.dry_run,
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error("Failed to create PR", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pr/status")
async def pr_status(req: PRStatusRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get PR status (open/draft/state) for a repo.
    """
    try:
        token = _get_token()
        if req.connector_name:
            from backend.services.connectors import get_connector

            conn = get_connector(
                db, user_id="default_user", provider="github", name=req.connector_name
            )
            if conn:
                token = conn.get("secrets", {}).get("token") or conn.get("secrets", {}).get("access_token") or token
        svc = GitHubWriteService(token=token)
        result = await svc.get_pr_status(req.repo_full_name, req.pr_number)
        return {"status": "ok", "pr": result}
    except Exception as e:
        logger.error("Failed to fetch PR status", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
