"""Organization Sync API Routes

These endpoints trigger synchronization of external data sources
(Jira, Confluence) into NAVI's conversational memory system.
"""

from typing import Optional, List
from datetime import date
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from backend.database.session import get_db
from backend.services.org_ingestor import ingest_jira_for_user, ingest_confluence_space
from backend.services.slack_ingestor import ingest_slack
from backend.services.teams_ingestor import ingest_teams
from backend.services.zoom_ingestor import ingest_zoom_meetings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/org", tags=["org-sync"])


# ============================================================================
# Request/Response Models
# ============================================================================


class JiraSyncRequest(BaseModel):
    """Request to sync Jira issues into NAVI memory"""

    user_id: str = Field(..., description="User identifier")
    max_issues: int = Field(20, ge=1, le=100, description="Maximum issues to sync")
    jql: Optional[str] = Field(None, description="Custom JQL query (optional)")


class JiraSyncResponse(BaseModel):
    """Response from Jira sync operation with snapshot tracking"""

    processed_keys: List[str] = Field(..., description="List of processed issue keys")
    total: int = Field(..., description="Total issues processed")
    user_id: str = Field(..., description="User identifier")
    snapshot_ts: str = Field(..., description="ISO timestamp when sync completed")
    success: bool = Field(True, description="Whether sync completed successfully")


class ConfluenceSyncRequest(BaseModel):
    """Request to sync Confluence pages into NAVI memory"""

    user_id: str = Field(..., description="User identifier")
    space_key: str = Field(..., description="Confluence space key (e.g., 'ENG')")
    limit: int = Field(20, ge=1, le=100, description="Maximum pages to sync")


class ConfluenceSyncResponse(BaseModel):
    """Response from Confluence sync operation"""

    processed_page_ids: List[str] = Field(..., description="List of processed page IDs")
    total: int = Field(..., description="Total pages processed")
    user_id: str = Field(..., description="User identifier")
    space_key: str = Field(..., description="Confluence space key")


class SlackSyncRequest(BaseModel):
    """Request to sync Slack messages into NAVI memory"""

    user_id: str = Field(..., description="User identifier")
    channels: List[str] = Field(..., description="List of Slack channel names to sync")
    limit: int = Field(200, ge=1, le=500, description="Maximum messages per channel")


class SlackSyncResponse(BaseModel):
    """Response from Slack sync operation"""

    processed_channel_ids: List[str] = Field(
        ..., description="List of processed channel IDs"
    )
    total: int = Field(..., description="Total channels processed")
    user_id: str = Field(..., description="User identifier")


class TeamsSyncRequest(BaseModel):
    """Request to sync Microsoft Teams messages into NAVI memory"""

    user_id: str = Field(..., description="User identifier")
    team_names: List[str] = Field(..., description="List of Teams team names to sync")
    channels: Optional[List[str]] = Field(
        None, description="Optional list of channel names to filter"
    )
    limit: int = Field(50, ge=1, le=200, description="Maximum messages per channel")


class TeamsSyncResponse(BaseModel):
    """Response from Teams sync operation"""

    processed_channel_keys: List[str] = Field(
        ..., description="List of 'team:channel' keys processed"
    )
    total: int = Field(..., description="Total channels processed")
    user_id: str = Field(..., description="User identifier")


class ZoomSyncRequest(BaseModel):
    """Request to sync Zoom meeting transcripts into NAVI memory"""

    user_id: str = Field(..., description="User identifier")
    zoom_user: Optional[str] = Field(
        None,
        description="Zoom user ID or email; uses AEP_ZOOM_USER_EMAIL if not provided",
    )
    from_date: date = Field(
        ..., description="Start date for meeting recordings (YYYY-MM-DD)"
    )
    to_date: date = Field(
        ..., description="End date for meeting recordings (YYYY-MM-DD)"
    )
    max_meetings: int = Field(
        20, ge=1, le=100, description="Maximum meetings to process"
    )


class ZoomSyncResponse(BaseModel):
    """Response from Zoom sync operation"""

    processed_meeting_ids: List[str] = Field(
        ..., description="List of meeting IDs processed"
    )
    total: int = Field(..., description="Total meetings processed")
    user_id: str = Field(..., description="User identifier")


class SyncStatusResponse(BaseModel):
    """Generic sync status response"""

    status: str
    message: str


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/sync/jira", response_model=JiraSyncResponse)
async def sync_jira(req: JiraSyncRequest, db: Session = Depends(get_db)):
    """
    Sync Jira issues into NAVI memory.

    This endpoint fetches Jira issues (assigned to current user by default)
    and stores them as task memories in NAVI's conversational memory system.

    **Example Request:**
    ```json
    {
        "user_id": "srinivas@example.com",
        "max_issues": 10,
        "jql": "assignee = currentUser() AND statusCategory != Done"
    }
    ```

    **What it does:**
    1. Fetches Jira issues using JQL query
    2. Summarizes each issue using LLM
    3. Stores summaries in navi_memory table (category=task)
    4. Returns list of processed issue keys

    **After sync:** NAVI will automatically know about your Jira tasks
    and reference them in conversations.
    """
    if not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    logger.info(
        "Jira sync requested",
        user_id=req.user_id,
        max_issues=req.max_issues,
        custom_jql=bool(req.jql),
    )

    try:
        keys = await ingest_jira_for_user(
            db=db,
            user_id=req.user_id.strip(),
            max_issues=req.max_issues,
            custom_jql=req.jql,
        )

        logger.info("Jira sync complete", user_id=req.user_id, processed=len(keys))

        # Add snapshot timestamp to all newly synced memories
        from datetime import datetime, timezone
        from sqlalchemy import text
        
        snapshot_ts = datetime.now(timezone.utc).isoformat()
        
        # Update all newly created Jira memories with sync timestamp
        db.execute(
            text("""
                UPDATE navi_memory
                SET meta_json = JSON_SET(
                    COALESCE(meta_json, '{}'),
                    '$.synced_at',
                    :synced_at
                )
                WHERE user_id = :user_id
                  AND category = 'task'
                  AND CAST(meta_json AS TEXT) LIKE '%\"source\": \"jira\"%'
                  AND updated_at >= datetime('now', '-5 minutes')
            """),
            {"user_id": req.user_id.strip(), "synced_at": snapshot_ts}
        )
        db.commit()

        return JiraSyncResponse(
            processed_keys=keys,
            total=len(keys),
            user_id=req.user_id,
            snapshot_ts=snapshot_ts,
            success=True
        )

    except RuntimeError as e:
        # Configuration error
        logger.error("Jira sync failed - configuration", error=str(e))
        raise HTTPException(
            status_code=503, detail=f"Jira integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error("Jira sync failed", error=str(e), user_id=req.user_id)
        raise HTTPException(status_code=500, detail=f"Jira sync failed: {str(e)}")


@router.post("/sync/confluence", response_model=ConfluenceSyncResponse)
async def sync_confluence(req: ConfluenceSyncRequest, db: Session = Depends(get_db)):
    """
    Sync Confluence pages into NAVI memory.

    This endpoint fetches pages from a Confluence space and stores them
    as workspace memories in NAVI's conversational memory system.

    **Example Request:**
    ```json
    {
        "user_id": "srinivas@example.com",
        "space_key": "ENG",
        "limit": 20
    }
    ```

    **What it does:**
    1. Fetches pages from specified Confluence space
    2. Converts HTML to plain text
    3. Summarizes each page using LLM
    4. Stores summaries in navi_memory table (category=workspace)
    5. Returns list of processed page IDs

    **After sync:** NAVI will automatically know about your documentation
    and reference it when answering questions.
    """
    if not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not req.space_key.strip():
        raise HTTPException(status_code=400, detail="space_key is required")

    logger.info(
        "Confluence sync requested",
        user_id=req.user_id,
        space_key=req.space_key,
        limit=req.limit,
    )

    try:
        page_ids = await ingest_confluence_space(
            db=db,
            user_id=req.user_id.strip(),
            space_key=req.space_key.strip(),
            limit=req.limit,
        )

        logger.info(
            "Confluence sync complete",
            user_id=req.user_id,
            space_key=req.space_key,
            processed=len(page_ids),
        )

        return ConfluenceSyncResponse(
            processed_page_ids=page_ids,
            total=len(page_ids),
            user_id=req.user_id,
            space_key=req.space_key,
        )

    except RuntimeError as e:
        # Configuration error
        logger.error("Confluence sync failed - configuration", error=str(e))
        raise HTTPException(
            status_code=503, detail=f"Confluence integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Confluence sync failed",
            error=str(e),
            user_id=req.user_id,
            space_key=req.space_key,
        )
        raise HTTPException(status_code=500, detail=f"Confluence sync failed: {str(e)}")


@router.post("/sync/slack", response_model=SlackSyncResponse)
async def sync_slack(req: SlackSyncRequest, db: Session = Depends(get_db)):
    """
    Sync Slack messages into NAVI memory.

    This endpoint fetches Slack messages from specified channels and stores them
    as interaction memories in NAVI's conversational memory system.

    **Example Request:**
    ```json
    {
        "user_id": "srinivas@example.com",
        "channels": ["eng-backend", "specimen-collection"],
        "limit": 50
    }
    ```

    **What it does:**
    - Fetches recent messages from specified Slack channels
    - Groups messages by thread
    - Summarizes discussions with LLM
    - Detects Jira ticket references
    - Stores in memory with embeddings for RAG search

    Args:
        req: Slack sync request parameters
        db: Database session (injected)

    Returns:
        List of processed channel IDs

    Raises:
        HTTPException: If sync fails or Slack is not configured
    """
    user_id = req.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not req.channels:
        raise HTTPException(status_code=400, detail="channels list cannot be empty")

    logger.info(
        "Slack sync requested",
        user_id=user_id,
        channels=req.channels,
        limit=req.limit,
    )

    try:
        channel_ids = await ingest_slack(
            db=db,
            user_id=user_id,
            channels=req.channels,
            limit=req.limit,
        )

        logger.info(
            "Slack sync completed",
            user_id=user_id,
            processed_count=len(channel_ids),
        )

        return SlackSyncResponse(
            processed_channel_ids=channel_ids,
            total=len(channel_ids),
            user_id=user_id,
        )

    except RuntimeError as e:
        logger.error("Slack integration not configured", error=str(e))
        raise HTTPException(
            status_code=503, detail=f"Slack integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Slack sync failed",
            error=str(e),
            user_id=req.user_id,
            channels=req.channels,
        )
        raise HTTPException(status_code=500, detail=f"Slack sync failed: {str(e)}")


@router.post("/sync/teams", response_model=TeamsSyncResponse)
async def sync_teams(req: TeamsSyncRequest, db: Session = Depends(get_db)):
    """
    Sync Microsoft Teams messages into NAVI memory.

    This endpoint fetches Teams messages from specified teams/channels and stores them
    as interaction memories in NAVI's conversational memory system.

    **Example Request:**
    ```json
    {
        "user_id": "srinivas@example.com",
        "team_names": ["Engineering"],
        "channels": ["General", "Sprint"],
        "limit": 30
    }
    ```

    **What it does:**
    - Fetches recent messages from Teams channels
    - Summarizes discussions with LLM
    - Detects Jira ticket references
    - Stores in memory with embeddings for RAG search

    Args:
        req: Teams sync request parameters
        db: Database session (injected)

    Returns:
        List of processed "team:channel" keys

    Raises:
        HTTPException: If sync fails or Teams is not configured
    """
    user_id = req.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not req.team_names:
        raise HTTPException(status_code=400, detail="team_names list cannot be empty")

    logger.info(
        "Teams sync requested",
        user_id=user_id,
        team_names=req.team_names,
        limit=req.limit,
    )

    try:
        channel_keys = await ingest_teams(
            db=db,
            user_id=user_id,
            team_names=req.team_names,
            channels_per_team=req.channels,
            limit=req.limit,
        )

        logger.info(
            "Teams sync completed",
            user_id=user_id,
            processed_count=len(channel_keys),
        )

        return TeamsSyncResponse(
            processed_channel_keys=channel_keys,
            total=len(channel_keys),
            user_id=user_id,
        )

    except RuntimeError as e:
        logger.error("Teams integration not configured", error=str(e))
        raise HTTPException(
            status_code=503, detail=f"Teams integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Teams sync failed",
            error=str(e),
            user_id=req.user_id,
            team_names=req.team_names,
        )
        raise HTTPException(status_code=500, detail=f"Teams sync failed: {str(e)}")


@router.post("/sync/zoom", response_model=ZoomSyncResponse)
async def sync_zoom(req: ZoomSyncRequest, db: Session = Depends(get_db)):
    """
    Sync Zoom meeting transcripts into NAVI memory.

    This endpoint fetches Zoom meeting recordings with transcripts from specified
    date range and stores them as interaction memories in NAVI's conversational memory system.

    **Example Request:**
    ```json
    {
        "user_id": "srinivas@example.com",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "max_meetings": 10
    }
    ```

    **What it does:**
    - Fetches cloud recordings with transcripts from Zoom
    - Cleans and summarizes meeting discussions with LLM
    - Detects Jira ticket references
    - Stores in memory with embeddings for RAG search

    Args:
        req: Zoom sync request parameters
        db: Database session (injected)

    Returns:
        List of processed meeting IDs

    Raises:
        HTTPException: If sync fails or Zoom is not configured
    """
    user_id = req.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    zoom_user = req.zoom_user or os.getenv("AEP_ZOOM_USER_EMAIL", "").strip()
    if not zoom_user:
        raise HTTPException(
            status_code=400,
            detail="zoom_user or AEP_ZOOM_USER_EMAIL must be set",
        )

    logger.info(
        "Zoom sync requested",
        user_id=user_id,
        zoom_user=zoom_user,
        from_date=str(req.from_date),
        to_date=str(req.to_date),
        max_meetings=req.max_meetings,
    )

    try:
        meeting_ids = await ingest_zoom_meetings(
            db=db,
            user_id=user_id,
            zoom_user=zoom_user,
            from_date=req.from_date,
            to_date=req.to_date,
            max_meetings=req.max_meetings,
        )

        logger.info(
            "Zoom sync completed",
            user_id=user_id,
            processed_count=len(meeting_ids),
        )

        return ZoomSyncResponse(
            processed_meeting_ids=meeting_ids,
            total=len(meeting_ids),
            user_id=user_id,
        )

    except RuntimeError as e:
        logger.error("Zoom integration not configured", error=str(e))
        raise HTTPException(
            status_code=503, detail=f"Zoom integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Zoom sync failed",
            error=str(e),
            user_id=req.user_id,
            zoom_user=zoom_user,
        )
        raise HTTPException(status_code=500, detail=f"Zoom sync failed: {str(e)}")


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status():
    """
    Check org sync service status.

    Returns:
        Status of the organization sync service
    """
    return SyncStatusResponse(
        status="ok",
        message="Organization sync service is running. Available endpoints: /sync/jira, /sync/confluence, /sync/slack, /sync/teams, /sync/zoom",
    )
