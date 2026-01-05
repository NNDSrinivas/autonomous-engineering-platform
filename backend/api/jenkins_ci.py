"""
Jenkins CI control using saved connectors (or env JENKINS_* variables).
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

router = APIRouter(prefix="/api/jenkins/ci", tags=["jenkins-ci"])


def _resolve_user_id(current_user: Any = Depends(get_current_user)) -> str:  # type: ignore[name-defined]
    if hasattr(current_user, "id"):
        return str(current_user.id)
    if hasattr(current_user, "sub"):
        return str(current_user.sub)
    return str(current_user)


def _resolve_connector(
    db: Session, user_id: str, connector_name: Optional[str]
) -> Dict[str, str]:
    from os import getenv

    base_url = getenv("JENKINS_BASE_URL", "")
    username = getenv("JENKINS_USER", "")
    token = getenv("JENKINS_TOKEN", "")

    if connector_name and connectors_service.connectors_available(db):
        conn = connectors_service.get_connector(
            db, user_id=user_id, provider="jenkins", name=connector_name
        )
        if conn:
            cfg = conn.get("config", {}) or {}
            secrets = conn.get("secrets", {}) or {}
            base_url = cfg.get("base_url", base_url)
            username = cfg.get("username", username)
            token = secrets.get("token") or secrets.get("api_token") or token

    if not base_url or not token:
        raise HTTPException(
            status_code=500,
            detail="Configure Jenkins connector or set JENKINS_BASE_URL/JENKINS_TOKEN",
        )

    return {"base_url": base_url.rstrip("/"), "username": username, "token": token}


class JenkinsDispatch(BaseModel):
    job_path: str = Field(..., description="Jenkins job path, e.g., folder/job-name")
    parameters: Dict[str, str] = Field(default_factory=dict)
    connector_name: Optional[str] = None


class JenkinsStatus(BaseModel):
    job_path: str
    build_number: int
    connector_name: Optional[str] = None


async def _client(base_url: str, username: str, token: str):
    auth = (username, token) if username else (token, "")
    return httpx.AsyncClient(
        base_url=base_url,
        auth=auth,
        timeout=30.0,
        headers={"User-Agent": "AutonomousEngineeringPlatform/1.0"},
    )


@router.post("/dispatch")
async def dispatch(
    req: JenkinsDispatch,
    db: Session = Depends(get_db),
    user_id: str = Depends(_resolve_user_id),
):
    resolved = _resolve_connector(
        db, user_id=user_id, connector_name=req.connector_name
    )
    try:
        async with await _client(
            resolved["base_url"], resolved["username"], resolved["token"]
        ) as client:
            endpoint = f"/job/{req.job_path}/buildWithParameters"
            resp = await client.post(endpoint, data=req.parameters or {})
            if resp.status_code not in (200, 201, 202):
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            ci_run = CiRun(
                provider="jenkins",
                repo=req.job_path,
                workflow="job",
                run_id="pending",
                status="queued",
                url=resp.headers.get("Location"),
                user_id=user_id,
            )
            try:
                db.add(ci_run)
                db.commit()
            except Exception:
                db.rollback()

            return {"status": "triggered", "location": resp.headers.get("Location")}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/status")
async def status(
    req: JenkinsStatus,
    db: Session = Depends(get_db),
    user_id: str = Depends(_resolve_user_id),
):
    resolved = _resolve_connector(
        db, user_id=user_id, connector_name=req.connector_name
    )
    try:
        async with await _client(
            resolved["base_url"], resolved["username"], resolved["token"]
        ) as client:
            endpoint = f"/job/{req.job_path}/{req.build_number}/api/json"
            resp = await client.get(endpoint)
            resp.raise_for_status()
            return {"status": "ok", "build": resp.json()}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
