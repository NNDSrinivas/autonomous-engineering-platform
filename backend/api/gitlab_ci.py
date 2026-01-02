"""
GitLab CI pipeline control using saved connectors (or PAT from env).
"""

from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.auth.deps import get_current_user
from backend.core.db import get_db
from backend.models.ci_run import CiRun
from backend.services import connectors as connectors_service

router = APIRouter(prefix="/api/gitlab/ci", tags=["gitlab-ci"])


def _resolve_user_id(current_user: Any = Depends(get_current_user)) -> str:  # type: ignore[name-defined]
    if hasattr(current_user, "id"):
        return str(current_user.id)
    if hasattr(current_user, "sub"):
        return str(current_user.sub)
    return str(current_user)


def _resolve_connector(db: Session, user_id: str, connector_name: Optional[str]) -> Dict[str, str]:
    base_url = "https://gitlab.com/api/v4"
    token = ""

    if connector_name and connectors_service.connectors_available(db):
        conn = connectors_service.get_connector(db, user_id=user_id, provider="gitlab", name=connector_name)
        if conn:
            token = conn.get("secrets", {}).get("token") or ""
            base_url = conn.get("config", {}).get("base_url", base_url)

    if not token:
        from os import getenv

        token = getenv("GITLAB_TOKEN", "")
        base_url = getenv("GITLAB_API_BASE", base_url)

    if not token:
        raise HTTPException(status_code=500, detail="Configure a GitLab connector or set GITLAB_TOKEN")

    return {"token": token, "base_url": base_url}


class GitLabDispatch(BaseModel):
    project_id: str = Field(..., description="Project ID or URL-encoded path")
    ref: str = Field(..., description="Branch/tag to build")
    variables: Dict[str, str] = Field(default_factory=dict)
    connector_name: Optional[str] = Field(None, description="Saved connector name (default)")


class GitLabStatus(BaseModel):
    project_id: str
    pipeline_id: int
    connector_name: Optional[str] = None


async def _client(base_url: str, token: str):
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers={
            "Private-Token": token,
            "User-Agent": "AutonomousEngineeringPlatform/1.0",
        },
        timeout=30.0,
    )


@router.post("/dispatch")
async def dispatch(req: GitLabDispatch, db: Session = Depends(get_db), user_id: str = Depends(_resolve_user_id)):
    resolved = _resolve_connector(db, user_id=user_id, connector_name=req.connector_name)
    try:
        async with await _client(resolved["base_url"], resolved["token"]) as client:
            resp = await client.post(
                f"/projects/{req.project_id}/pipeline",
                json={"ref": req.ref, "variables": [{"key": k, "value": v} for k, v in (req.variables or {}).items()]},
            )
            if resp.status_code not in (200, 201, 202):
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            payload = resp.json()

            try:
                ci_run = CiRun(
                    provider="gitlab",
                    repo=req.project_id,
                    workflow="pipeline",
                    run_id=str(payload.get("id")),
                    status=payload.get("status"),
                    url=payload.get("web_url"),
                    user_id=user_id,
                )
                db.add(ci_run)
                db.commit()
            except Exception:
                db.rollback()

            return {"status": "triggered", "pipeline": payload}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/status")
async def status(req: GitLabStatus, db: Session = Depends(get_db), user_id: str = Depends(_resolve_user_id)):
    resolved = _resolve_connector(db, user_id=user_id, connector_name=req.connector_name)
    try:
        async with await _client(resolved["base_url"], resolved["token"]) as client:
            resp = await client.get(f"/projects/{req.project_id}/pipelines/{req.pipeline_id}")
            resp.raise_for_status()
            return {"status": "ok", "pipeline": resp.json()}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
