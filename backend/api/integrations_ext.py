"""Extended Integrations API - Connection management for Slack, Confluence, etc."""

import os
import logging
from fastapi import APIRouter, Body, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.db import get_db

logger = logging.getLogger(__name__)

# GitHub issue tracking token encryption implementation
GITHUB_ISSUE_TOKEN_ENCRYPTION = (
    "https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18"
)

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
    # Fail closed by default: require explicit opt-in for development mode
    # If ENVIRONMENT is not set or not in whitelist, assume production and block
    environment = os.getenv("ENVIRONMENT")
    if environment is None:
        raise HTTPException(
            status_code=501,
            detail=f"ENVIRONMENT variable not set. Token encryption not implemented. See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )
    environment = environment.lower()
    # Configurable whitelist with narrow default (development-only)
    # Use ALLOWED_ENVIRONMENTS env var (comma-separated) to customize
    # Example: ALLOWED_ENVIRONMENTS="development,staging" allows both dev and staging
    allowed_environments_raw = os.getenv(
        "ALLOWED_ENVIRONMENTS", "development,dev,local"
    )
    allowed_environments = {
        env.strip().lower()
        for env in allowed_environments_raw.split(",")
        if env.strip()
    }
    if environment not in allowed_environments:
        raise HTTPException(
            status_code=501,
            detail=f"Token encryption not implemented. Production deployment blocked (ENVIRONMENT={environment}). See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )

    # SECURITY WARNING: Tokens are currently stored in plaintext in the database.
    # This is acceptable for development/testing but NOT for production deployment.
    # See SECURITY.md and README.md for detailed security considerations.
    # TODO: BEFORE PRODUCTION - Implement token encryption at rest (CRITICAL)
    # Options:
    #  - Use a secrets-management service (AWS KMS + Secrets Manager, HashiCorp Vault)
    #  - Use database TDE/column-level encryption if available
    #  - Application-level AES/GCM encryption with key stored in an HSM or KMS
    # If application-level encryption is used, load the encryption key from an
    # environment-backed secret (e.g. env var referencing the KMS key) and
    # rotate keys periodically.
    # TRACKING: GitHub Issue #18 - Implement token encryption before production deployment
    # https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18
    logger.warning(
        "Development mode: Storing tokens in plaintext. See SECURITY.md for production requirements."
    )
    # Use ON CONFLICT to handle existing connections (update token and timestamp)
    db.execute(
        text(
            """
            INSERT INTO slack_connection (org_id, bot_token, team_id) 
            VALUES (:o,:t,:team)
            ON CONFLICT (org_id, team_id) DO UPDATE SET 
                bot_token=:t, 
                updated_at=CURRENT_TIMESTAMP
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
    # Fail closed by default: require explicit opt-in for development mode
    # If ENVIRONMENT is not set or not in whitelist, assume production and block
    environment = os.getenv("ENVIRONMENT")
    if environment is None:
        raise HTTPException(
            status_code=501,
            detail=f"ENVIRONMENT variable not set. Token encryption not implemented. See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )
    environment = environment.lower()
    # Configurable whitelist with narrow default (development-only)
    # Use ALLOWED_ENVIRONMENTS env var (comma-separated) to customize
    # Example: ALLOWED_ENVIRONMENTS="development,staging" allows both dev and staging
    allowed_environments_raw = os.getenv(
        "ALLOWED_ENVIRONMENTS", "development,dev,local"
    )
    allowed_environments = {
        env.strip().lower()
        for env in allowed_environments_raw.split(",")
        if env.strip()
    }
    if environment not in allowed_environments:
        raise HTTPException(
            status_code=501,
            detail=f"Token encryption not implemented. Production deployment blocked (ENVIRONMENT={environment}). See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )

    # TODO: Security improvement - encrypt tokens at rest (same as Slack tokens above)
    # See SECURITY.md for detailed security considerations.
    logger.warning(
        "Development mode: Storing tokens in plaintext. See SECURITY.md for production requirements."
    )
    # Use ON CONFLICT to handle existing connections (update credentials and timestamp)
    db.execute(
        text(
            """
            INSERT INTO confluence_connection (org_id, base_url, access_token, email) 
            VALUES (:o,:b,:a,:e)
            ON CONFLICT (org_id, base_url) DO UPDATE SET 
                access_token=:a, 
                email=:e, 
                updated_at=CURRENT_TIMESTAMP
            """
        ),
        {"o": org, "b": base, "a": token, "e": email},
    )
    db.commit()
    return {"ok": True}
