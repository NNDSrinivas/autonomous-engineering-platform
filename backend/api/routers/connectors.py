from __future__ import annotations

import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ...core.db import get_db
from ...services.jira import JiraService
from ...services.github import GitHubService
from ...models.integrations import (
    JiraConnection,
    JiraProjectConfig,
    GhConnection,
    GhRepo,
)
from ...core.auth.deps import get_current_user, get_current_user_optional
from ...core.auth.models import User
from ...services.org_ingestor import ingest_jira_for_user
import httpx


router = APIRouter(prefix="/api/connectors", tags=["connectors"])

# All supported connector providers
ALL_PROVIDERS = ["jira", "github", "slack", "teams", "zoom", "jenkins", "generic_http"]


class ApiKeyConnectBody(BaseModel):
    base_url: str
    api_token: str
    email: str | None = None


class ConnectorStatus(BaseModel):
    """Status for a single connector provider"""
    provider: str
    status: str  # "connected" | "disconnected" | "error"
    last_sync_ts: Optional[str] = None
    last_index_ts: Optional[str] = None
    message: Optional[str] = None


class ConnectorsStatusResponse(BaseModel):
    """Combined status for all connector providers"""
    connectors: List[ConnectorStatus]


def get_status_for_provider(provider: str, db: Session) -> ConnectorStatus:
    """Helper to get status for a single provider (reusable by both endpoints)"""
    provider = provider.lower()
    
    if provider == "jira":
        try:
            # Get user context from environment (development mode)
            org_id = os.getenv("DEV_ORG_ID", "test-org")
            user_id = os.getenv("DEV_USER_ID", "test-user")
            
            # Query database for active connection - use simple query instead of filter_by
            connection = db.query(JiraConnection).filter(
                JiraConnection.org_id == org_id,
                JiraConnection.user_id == user_id
            ).first()
            
            if connection and connection.access_token:
                return ConnectorStatus(
                    provider=provider,
                    status="connected",
                    message="Jira connected"
                )
            else:
                return ConnectorStatus(
                    provider=provider,
                    status="disconnected",
                    message="Jira not connected"
                )
        except Exception as e:
            # Log the actual error for debugging
            import traceback
            print(f"Status check error for {provider}: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            # Return disconnected status gracefully
            return ConnectorStatus(
                provider=provider,
                status="disconnected",
                message=f"Jira status check failed: {str(e)}"
            )
    
    # Default: disconnected status for all other providers
    return ConnectorStatus(
        provider=provider,
        status="disconnected",
        message=f"{provider.title()} not connected"
    )


@router.get("/status", response_model=ConnectorsStatusResponse)
def get_all_connectors_status(db: Session = Depends(get_db)):
    """Get status for all connector providers in a single call"""
    statuses: List[ConnectorStatus] = []
    for provider in ALL_PROVIDERS:
        status = get_status_for_provider(provider, db)
        statuses.append(status)
    return ConnectorsStatusResponse(connectors=statuses)


@router.get("/{provider}/status", response_model=ConnectorStatus)
def connector_status(provider: str, db: Session = Depends(get_db)):
    """Get status for a single connector provider"""
    return get_status_for_provider(provider, db)


@router.post("/{provider}/connect")
async def connector_connect(
    provider: str,
    body: ApiKeyConnectBody,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Connect to an external service provider.
    
    For development: Works without authentication (uses fallback user/org).
    For production: Requires authenticated user.
    """
    provider = provider.lower()
    
    # Determine user context (auth user or dev fallback)
    if user:
        user_id = user.user_id
        org_id = user.org_id
    else:
        # Development fallback - use configured dev user from environment
        import os
        user_id = os.getenv("DEV_USER_ID", "default_user")
        org_id = os.getenv("DEV_ORG_ID", "default-org")
    
    if provider == "jira":
        # --- 1) Quick credential validation ---
        base = body.base_url.rstrip("/")
        validation_success = False
        validation_error = None

        try:
            # keep timeout modest so this never hangs the UI
            async with httpx.AsyncClient(timeout=10.0) as http:
                # Attempt 1: Bearer token (OAuth-style)
                r_bearer = await http.get(
                    f"{base}/rest/api/3/myself",
                    headers={
                        "Authorization": f"Bearer {body.api_token}",
                        "Accept": "application/json",
                    },
                )

                if r_bearer.status_code == 200:
                    validation_success = True
                elif body.email:
                    # Attempt 2: Basic auth (email + API token)
                    r_basic = await http.get(
                        f"{base}/rest/api/3/myself",
                        auth=(body.email, body.api_token),
                        headers={"Accept": "application/json"},
                    )
                    if r_basic.status_code == 200:
                        validation_success = True
                    else:
                        validation_error = (
                            f"Basic auth failed: {r_basic.status_code} "
                            f"{r_basic.text[:120]}"
                        )
                else:
                    validation_error = (
                        f"Bearer auth failed: {r_bearer.status_code} "
                        f"and no email provided for Basic auth"
                    )

            if not validation_success:
                raise HTTPException(
                    status_code=400,
                    detail=validation_error or "Jira credential validation failed",
                )

        except HTTPException:
            # bubble up cleanly so frontend shows a proper error
            raise
        except Exception as e:
            # network / DNS / SSL, etc.
            raise HTTPException(
                status_code=400,
                detail=f"Failed to validate Jira credentials: {str(e)}",
            )

        # --- 2) Save connection scoped to user (fast DB write) ---
        conn = JiraService.save_connection(
            db,
            base_url=base,
            access_token=body.api_token,
            user_id=user_id,
            org_id=org_id,
        )

        # --- 3) Trigger ingestion for immediate testing (fire-and-forget) ---
        try:
            # Import here to avoid circular imports
            from ...services.org_ingestor import ingest_jira_for_user
            
            # Fire-and-forget ingestion (don't await, don't block response)
            import asyncio
            asyncio.create_task(ingest_jira_for_user(
                db=db,
                user_id=user_id, 
                max_issues=20,
                custom_jql=None
            ))
        except Exception as e:
            # Log but don't fail the connection
            print(f"Warning: Failed to trigger Jira ingestion: {e}")

        return {
            "ok": True,
            "status": "connected",
            "connection_id": conn.id,
            "provider": "jira",
        }

    # Other API key based connectors not implemented yet
    raise HTTPException(status_code=501, detail=f"Connect flow for '{provider}' not implemented")


@router.post("/jira/sync-now")
async def jira_sync_now(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Dev-only endpoint to force a Jira ingest into NAVI memory.
    
    - If user is authenticated, use their user/org.
    - If not, fall back to DEV_ env vars / default_user for local dev.
    """
    import logging
    from ...services.org_ingestor import ingest_jira_for_user
    
    logger = logging.getLogger(__name__)
    
    if user:
        user_id = user.user_id
        org_id = user.org_id
    else:
        user_id = os.getenv("DEV_USER_ID", "default_user")
        org_id = os.getenv("DEV_ORG_ID", "default-org")

    max_issues = int(os.getenv("JIRA_DEV_SYNC_LIMIT", "50"))

    logger.info(
        f"[JIRA-SYNC] Manual sync triggered for user_id={user_id}, org_id={org_id}, max_issues={max_issues}"
    )

    try:
        count = await ingest_jira_for_user(
            db=db,
            user_id=user_id,
            max_issues=max_issues,
            custom_jql=None,
        )
        
        logger.info(f"[JIRA-SYNC] Successfully synced {count} issues for user {user_id}")
        
        return {
            "ok": True,
            "provider": "jira",
            "synced_issues": count,
            "user_id": user_id,
            "org_id": org_id,
        }
    except Exception as e:
        logger.error(f"[JIRA-SYNC] Failed to sync for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Jira sync failed: {str(e)}")


class OAuthStartOut(BaseModel):
    url: str


@router.post("/{provider}/start-oauth", response_model=OAuthStartOut)
def connector_start_oauth(provider: str):
    provider = provider.lower()
    # Minimal placeholder URLs for OAuth/App setup pages
    urls = {
        "slack": "https://api.slack.com/apps",
        "teams": "https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/enable-sso",
        "zoom": "https://marketplace.zoom.us/",
        "github": "https://github.com/settings/tokens",
        "jira": "https://id.atlassian.com/manage-profile/security/api-tokens",
    }
    url = urls.get(provider)
    if not url:
        raise HTTPException(status_code=501, detail=f"OAuth start for '{provider}' not implemented")
    return OAuthStartOut(url=url)
