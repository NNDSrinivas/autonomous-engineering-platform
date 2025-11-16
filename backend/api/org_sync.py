"""Organization Sync API Routes

These endpoints trigger synchronization of external data sources
(Jira, Confluence) into NAVI's conversational memory system.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from backend.database.session import get_db
from backend.services.org_ingestor import ingest_jira_for_user, ingest_confluence_space

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
    """Response from Jira sync operation"""
    processed_keys: List[str] = Field(..., description="List of processed issue keys")
    total: int = Field(..., description="Total issues processed")
    user_id: str = Field(..., description="User identifier")


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
        custom_jql=bool(req.jql)
    )
    
    try:
        keys = await ingest_jira_for_user(
            db=db,
            user_id=req.user_id.strip(),
            max_issues=req.max_issues,
            custom_jql=req.jql,
        )
        
        logger.info("Jira sync complete", user_id=req.user_id, processed=len(keys))
        
        return JiraSyncResponse(
            processed_keys=keys,
            total=len(keys),
            user_id=req.user_id,
        )
        
    except RuntimeError as e:
        # Configuration error
        logger.error("Jira sync failed - configuration", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Jira integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error("Jira sync failed", error=str(e), user_id=req.user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Jira sync failed: {str(e)}"
        )


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
        limit=req.limit
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
            processed=len(page_ids)
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
            status_code=503,
            detail=f"Confluence integration not configured: {str(e)}"
        )
    except Exception as e:
        logger.error(
            "Confluence sync failed",
            error=str(e),
            user_id=req.user_id,
            space_key=req.space_key
        )
        raise HTTPException(
            status_code=500,
            detail=f"Confluence sync failed: {str(e)}"
        )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status():
    """
    Check org sync service status.
    
    Returns:
        Status of the organization sync service
    """
    return SyncStatusResponse(
        status="ok",
        message="Organization sync service is running. Available endpoints: /sync/jira, /sync/confluence"
    )
