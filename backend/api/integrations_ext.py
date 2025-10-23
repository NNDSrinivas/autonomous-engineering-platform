"""Extended Integrations API - Connection management for Slack, Confluence, etc."""

from fastapi import APIRouter, Body, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db

router = APIRouter(prefix="/api/integrations-ext", tags=["integrations-ext"])


@router.post("/slack/connect")
def slack_connect(
    payload: dict = Body(...), request: Request = None, db: Session = Depends(get_db)
):
    """Connect Slack workspace with bot token"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    token = payload.get("bot_token")
    team = payload.get("team_id")
    if not token:
        raise HTTPException(400, "bot_token required")
    db.execute(
        text(
            "INSERT INTO slack_connection (org_id, bot_token, team_id) VALUES (:o,:t,:team)"
        ),
        {"o": org, "t": token, "team": team},
    )
    db.commit()
    return {"ok": True}


@router.post("/confluence/connect")
def confluence_connect(
    payload: dict = Body(...), request: Request = None, db: Session = Depends(get_db)
):
    """Connect Confluence workspace with access token"""
    org = request.headers.get("X-Org-Id")
    if not org:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    base = payload.get("base_url")
    token = payload.get("access_token")
    email = payload.get("email")
    if not base or not token:
        raise HTTPException(400, "base_url and access_token required")
    db.execute(
        text(
            "INSERT INTO confluence_connection (org_id, base_url, access_token, email) VALUES (:o,:b,:a,:e)"
        ),
        {"o": org, "b": base, "a": token, "e": email},
    )
    db.commit()
    return {"ok": True}
