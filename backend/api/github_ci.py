"""
GitHub Actions CI control: trigger workflow dispatch and fetch run status.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import httpx
import os
import logging

from backend.core.db import get_db
from sqlalchemy.orm import Session
from backend.services import connectors as connectors_service
from backend.models.ci_run import CiRun
from backend.core.auth.deps import get_current_user

router = APIRouter(prefix="/api/github/ci", tags=["github-ci"])
logger = logging.getLogger(__name__)


def _token_from_env() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    if not token:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_TOKEN (or GH_TOKEN) is required or configure a GitHub connector.",
        )
    return token


class CITrigger(BaseModel):
    repo_full_name: str = Field(..., description="owner/repo")
    workflow: str = Field(
        ..., description="workflow file name (e.g., ci.yml) or workflow id"
    )
    ref: str = Field(..., description="branch/tag to run")
    inputs: Dict[str, Any] = Field(default_factory=dict)
    connector_name: Optional[str] = Field(None, description="Connector name (default)")


class CIStatus(BaseModel):
    repo_full_name: str
    run_id: int
    connector_name: Optional[str] = None


def _resolve_user_id(current_user: Any = Depends(get_current_user)) -> str:  # type: ignore[name-defined]
    if hasattr(current_user, "id"):
        return str(current_user.id)
    if hasattr(current_user, "sub"):
        return str(current_user.sub)
    return str(current_user)


def _resolve_token_and_base(
    db: Session, user_id: str, connector_name: Optional[str]
) -> Dict[str, str]:
    """
    Resolve token/base_url from a saved connector; fallback to env.
    """
    token = None
    base_url = "https://api.github.com"

    if connector_name and connectors_service.connectors_available(db):
        conn = connectors_service.get_connector(
            db, user_id=user_id, provider="github", name=connector_name
        )
        if conn:
            token = conn.get("secrets", {}).get("token") or conn.get("secrets", {}).get(
                "access_token"
            )
            base_url = conn.get("config", {}).get("base_url", base_url)

    if not token:
        token = _token_from_env()

    return {"token": token, "base_url": base_url}


async def _client(base_url: str, token: str):
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AutonomousEngineeringPlatform/1.0",
        },
        timeout=30.0,
    )


@router.post("/dispatch")
async def dispatch(
    req: CITrigger,
    db: Session = Depends(get_db),
    user_id: str = Depends(_resolve_user_id),
):
    """
    Trigger a GitHub Actions workflow dispatch and return the latest run for that ref/workflow.
    """
    try:
        resolved = _resolve_token_and_base(
            db, user_id=user_id, connector_name=req.connector_name
        )
        async with await _client(resolved["base_url"], resolved["token"]) as client:
            resp = await client.post(
                f"/repos/{req.repo_full_name}/actions/workflows/{req.workflow}/dispatches",
                json={"ref": req.ref, "inputs": req.inputs or {}},
            )
            if resp.status_code not in (200, 201, 202, 204):
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            # Fetch latest run for this workflow/ref
            runs_resp = await client.get(
                f"/repos/{req.repo_full_name}/actions/runs",
                params={"branch": req.ref, "event": "workflow_dispatch"},
            )
            runs_resp.raise_for_status()
            runs = runs_resp.json().get("workflow_runs", [])
            run = runs[0] if runs else {}

            if run.get("id"):
                try:
                    ci_run = CiRun(
                        provider="github",
                        repo=req.repo_full_name,
                        workflow=str(req.workflow),
                        run_id=str(run.get("id")),
                        status=run.get("status"),
                        conclusion=run.get("conclusion"),
                        url=run.get("html_url"),
                        user_id=user_id,
                    )
                    db.add(ci_run)
                    db.commit()
                except Exception as db_err:
                    logger.warning("Failed to record CI run: %s", db_err, exc_info=True)

            return {
                "status": "triggered",
                "run": {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "html_url": run.get("html_url"),
                    "name": run.get("name"),
                    "head_branch": run.get("head_branch"),
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger GitHub Actions", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status")
async def status(
    req: CIStatus,
    db: Session = Depends(get_db),
    user_id: str = Depends(_resolve_user_id),
):
    """
    Get status of a GitHub Actions run by run_id.
    """
    try:
        resolved = _resolve_token_and_base(
            db, user_id=user_id, connector_name=req.connector_name
        )
        async with await _client(resolved["base_url"], resolved["token"]) as client:
            resp = await client.get(
                f"/repos/{req.repo_full_name}/actions/runs/{req.run_id}"
            )
            resp.raise_for_status()
            run = resp.json()
            return {
                "status": "ok",
                "run": {
                    "id": run.get("id"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "html_url": run.get("html_url"),
                    "name": run.get("name"),
                    "head_branch": run.get("head_branch"),
                },
            }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error("Failed to fetch GitHub Actions run status", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
