"""Extended Integrations API - Connection management for Slack, Confluence, etc."""

import os
import logging
from fastapi import APIRouter, Body, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import sqlalchemy
from ..core.db import get_db

logger = logging.getLogger(__name__)

# GitHub issue tracking token encryption implementation
GITHUB_ISSUE_TOKEN_ENCRYPTION = (
    "https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18"
)

router = APIRouter(prefix="/api/integrations-ext", tags=["integrations-ext"])


def _parse_allowed_environments(default: str = "development,local") -> set[str]:
    """
    Parse ALLOWED_ENVIRONMENTS env var into a set of lowercase environment names.

    Uses walrus operator to avoid calling strip() twice per iteration.
    Filters out empty strings after stripping whitespace.

    Args:
        default: Comma-separated default environments if env var not set

    Returns:
        Set of lowercase environment names
    """
    allowed_environments_raw = os.getenv("ALLOWED_ENVIRONMENTS", default)
    return {
        stripped.lower()
        for env in allowed_environments_raw.split(",")
        if (stripped := env.strip())
    }


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
            status_code=500,
            detail=f"ENVIRONMENT variable not set. Token encryption not implemented. See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )
    environment = environment.lower()
    # Configurable whitelist with narrow default (development-only)
    # Use ALLOWED_ENVIRONMENTS env var (comma-separated) to customize
    # Example: ALLOWED_ENVIRONMENTS="development,staging" allows both dev and staging
    allowed_environments = _parse_allowed_environments()
    if environment not in allowed_environments:
        raise HTTPException(
            status_code=500,
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
    # NOTE: SQLAlchemy logs parameters at DEBUG level. Do not enable DEBUG logging in
    # production as it would expose plaintext tokens. See SQLAlchemy echo=False in config.
    # REQUIREMENT: The slack_connection table MUST have a unique constraint on
    # (org_id, team_id) for this ON CONFLICT clause to work in SQLite and Postgres.
    # At runtime, verify the index for SQLite to provide an actionable error message
    # instead of failing with a cryptic database error.
    engine = getattr(db, "bind", None)
    # Get dialect name defensively and compare to 'sqlite' for readability
    dialect_name = getattr(getattr(engine, "dialect", None), "name", None)
    if dialect_name == "sqlite":
        try:
            idx_rows = list(db.execute(text("PRAGMA index_list('slack_connection')")))
            found = False
            for idx in idx_rows:
                # Prefer attribute access on Row objects, fall back to tuple indexing with robust error handling
                idx_name = getattr(idx, "name", None)
                if idx_name is None:
                    try:
                        # Defensive: PRAGMA index_list returns (seq, name, unique, origin, partial) in current SQLite
                        idx_name = idx[1]
                    except (IndexError, TypeError):
                        logger.error(
                            "Unexpected PRAGMA index_list row structure: %r. "
                            "Expected at least 2 elements for index name at position 1.",
                            idx,
                        )
                        continue
                if not idx_name:
                    continue
                info = list(db.execute(text(f"PRAGMA index_info('{idx_name}')")))
                # Extract column names with robust error handling for future SQLite version changes
                cols = []
                for r in info:
                    col_name = getattr(r, "name", None)
                    if col_name is not None:
                        cols.append(col_name)
                    elif (
                        isinstance(r, (tuple, list))
                        and len(r) > 2
                        and isinstance(r[2], str)
                    ):
                        # PRAGMA index_info returns (seqno, cid, name); index 2 is the column name
                        cols.append(r[2])
                    else:
                        logger.warning(
                            "Unexpected PRAGMA index_info row format: %r (expected 'name' attribute or string at index 2)",
                            r,
                        )
                        cols.append(None)
                if set(cols) == {"org_id", "team_id"}:
                    found = True
                    break
            if not found:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "slack_connection table must have a unique/index on (org_id, team_id) "
                        "for ON CONFLICT to work in SQLite. Check migrations or add the index."
                    ),
                )
        except sqlalchemy.exc.DatabaseError as e:
            logger.error("Error checking SQLite indexes for slack_connection: %s", e)

    try:
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
    except sqlalchemy.exc.DatabaseError as e:
        logger.error("Database error during Slack connect: %s", e)
        raise HTTPException(
            status_code=500,
            detail=(
                "Database error during Slack connect. Ensure slack_connection has a "
                "unique constraint on (org_id, team_id) and the database supports ON CONFLICT."
            ),
        )
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
            status_code=500,
            detail=f"ENVIRONMENT variable not set. Token encryption not implemented. See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )
    environment = environment.lower()
    # Configurable whitelist with narrow default (development-only)
    # Use ALLOWED_ENVIRONMENTS env var (comma-separated) to customize
    # Example: ALLOWED_ENVIRONMENTS="development,staging" allows both dev and staging
    allowed_environments = _parse_allowed_environments()
    if environment not in allowed_environments:
        raise HTTPException(
            status_code=500,
            detail=f"Token encryption not implemented. Production deployment blocked (ENVIRONMENT={environment}). See GitHub Issue #18: {GITHUB_ISSUE_TOKEN_ENCRYPTION}",
        )

    # TODO: Security improvement - encrypt tokens at rest (same as Slack tokens above)
    # See SECURITY.md for detailed security considerations.
    logger.warning(
        "Development mode: Storing tokens in plaintext. See SECURITY.md for production requirements."
    )
    # Use ON CONFLICT to handle existing connections (update credentials and timestamp)
    # NOTE: SQLAlchemy logs parameters at DEBUG level. Do not enable DEBUG logging in
    # production as it would expose plaintext tokens. See SQLAlchemy echo=False in config.
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
