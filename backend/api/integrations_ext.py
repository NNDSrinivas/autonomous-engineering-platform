"""Extended Integrations API - Connection management for Slack, Confluence, etc."""

import os
from fastapi import APIRouter, Body, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.db import get_db

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
        raise HTTPException(status_code=400, detail="bot_token required")

    # CRITICAL SECURITY CHECK: Prevent production deployment with plaintext tokens
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        raise HTTPException(
            status_code=501,
            detail="Token encryption not implemented. Production deployment blocked. See GitHub Issue #18: https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18",
        )

    # SECURITY WARNING: Tokens are currently stored in plaintext in the database.
    # This is acceptable for development/testing but NOT for production deployment.
    # TODO: BEFORE PRODUCTION - Implement token encryption at rest (CRITICAL)
    # Options:
    #  - Use a secrets-management service (AWS KMS + Secrets Manager, HashiCorp Vault)
    #  - Use database TDE/column-level encryption if available
    #  - Application-level AES/GCM encryption with key stored in an HSM or KMS
    # If application-level encryption is used, load the encryption key from an
    # environment-backed secret (e.g. env var referencing the KMS key) and
    # rotate keys periodically. See docs/security.md for recommended patterns.
    # TRACKING: GitHub Issue #18 - Implement token encryption before production deployment
    # https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18
    # Use ON CONFLICT to handle existing connections (update token)
    db.execute(
        text(
            """
            INSERT INTO slack_connection (org_id, bot_token, team_id) 
            VALUES (:o,:t,:team)
            ON CONFLICT (org_id, team_id) DO UPDATE SET bot_token=:t
            """
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
        raise HTTPException(
            status_code=400, detail="base_url and access_token required"
        )

    # CRITICAL SECURITY CHECK: Prevent production deployment with plaintext tokens
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        raise HTTPException(
            status_code=501,
            detail="Token encryption not implemented. Production deployment blocked. See GitHub Issue #18: https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18",
        )

    # TODO: Security improvement - encrypt tokens at rest (same as Slack tokens above)
    # Use ON CONFLICT to handle existing connections (update credentials)
    db.execute(
        text(
            """
            INSERT INTO confluence_connection (org_id, base_url, access_token, email) 
            VALUES (:o,:b,:a,:e)
            ON CONFLICT (org_id, base_url) DO UPDATE SET access_token=:a, email=:e
            """
        ),
        {"o": org, "b": base, "a": token, "e": email},
    )
    db.commit()
    return {"ok": True}
