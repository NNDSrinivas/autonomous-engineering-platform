"""
Phase 4.9 API Router — Long-Horizon Planning Endpoints

Provides REST API endpoints for autonomous planning and long-horizon execution.
Integrates with existing plan API and extends it with initiative-level capabilities.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.api.deps import get_current_user
from backend.agent.planning import (
    LongHorizonOrchestrator,
    OrchestrationMode,
    InitiativeConfig,
    CheckpointEngine,
    AdaptiveReplanner,
)


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/initiatives", tags=["Long-Horizon Planning"])


async def get_organization(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Resolve organization context from the current user."""
    org_id = current_user.get("org_id") or "default_org"
    return {"id": org_id}


# Pydantic models for API
class InitiativeCreateRequest(BaseModel):
    goal: str = Field(..., description="High-level goal for the initiative")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    jira_key: Optional[str] = Field(None, description="Associated Jira key")
    config: Optional[Dict[str, Any]] = Field(None, description="Initiative configuration")


class InitiativeResponse(BaseModel):
    id: str
    title: str
    goal: str
    status: str
    plan_id: str
    owner: str
    org_id: str
    jira_key: Optional[str]
    created_at: str
    updated_at: str
    progress: Optional[Dict[str, Any]] = None
    execution_status: Optional[Dict[str, Any]] = None


class CheckpointResponse(BaseModel):
    checkpoint_id: str
    initiative_id: str
    checkpoint_type: str
    created_at: str
    created_by: str
    description: str
    tags: List[str]
    progress_summary: Dict[str, Any]


class ReplanRequest(BaseModel):
    trigger: str = Field(..., description="Reason for replanning")
    trigger_details: Dict[str, Any] = Field(default_factory=dict)
    scope: str = Field("partial", description="Replan scope: minimal, partial, or full")


# Global orchestrator instance (in production, this would be injected)
_orchestrator_cache: Dict[str, LongHorizonOrchestrator] = {}


def get_orchestrator(db: Session = Depends(get_db)) -> LongHorizonOrchestrator:
    """Get or create orchestrator instance"""
    
    # Simple singleton pattern - in production, use proper DI
    cache_key = str(id(db))
    if cache_key not in _orchestrator_cache:
        _orchestrator_cache[cache_key] = LongHorizonOrchestrator(db)
    
    return _orchestrator_cache[cache_key]


@router.post("/", response_model=Dict[str, str])
async def create_initiative(
    request: InitiativeCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    organization = Depends(get_organization),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Create a new long-horizon initiative"""
    
    try:
        # Parse configuration
        config_dict = request.config or {}
        config = InitiativeConfig(
            orchestration_mode=OrchestrationMode(
                config_dict.get("orchestration_mode", "DEVELOPMENT")
            ),
            auto_checkpoint_interval_minutes=config_dict.get("auto_checkpoint_interval_minutes", 30),
            max_execution_hours=config_dict.get("max_execution_hours", 168),
            auto_approve_low_risk=config_dict.get("auto_approve_low_risk", True),
            require_milestone_approval=config_dict.get("require_milestone_approval", True),
            max_replan_attempts=config_dict.get("max_replan_attempts", 3),
            enable_adaptive_replanning=config_dict.get("enable_adaptive_replanning", True),
        )
        
        # Start initiative
        initiative_id = await orchestrator.start_initiative(
            goal=request.goal,
            context=request.context,
            org_id=organization["id"],
            owner=current_user["id"],
            config=config,
            jira_key=request.jira_key
        )
        
        logger.info(f"Created initiative {initiative_id} for user {current_user['id']}")
        
        return {
            "initiative_id": initiative_id,
            "message": "Initiative created successfully",
            "status": "planned"
        }
        
    except Exception as e:
        logger.error(f"Failed to create initiative: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create initiative: {str(e)}"
        )


@router.get("/", response_model=List[InitiativeResponse])
async def list_initiatives(
    status_filter: Optional[str] = None,
    owner_filter: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    organization = Depends(get_organization),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """List initiatives for the organization"""
    
    try:
        # Get initiatives from orchestrator
        active_initiatives = orchestrator.list_active_initiatives(organization["id"])
        
        # Filter if requested
        if status_filter:
            active_initiatives = [
                init for init in active_initiatives
                if init.get("status") == status_filter
            ]
        
        if owner_filter:
            active_initiatives = [
                init for init in active_initiatives
                if init.get("owner") == owner_filter
            ]
        
        # Limit results
        active_initiatives = active_initiatives[:limit]
        
        # Convert to response format
        responses = []
        for init_data in active_initiatives:
            response = InitiativeResponse(
                id=init_data["id"],
                title=init_data["title"],
                goal=init_data["goal"],
                status=init_data["status"],
                plan_id=init_data["plan_id"],
                owner=init_data["owner"],
                org_id=init_data["org_id"],
                jira_key=init_data.get("jira_key"),
                created_at=init_data["created_at"],
                updated_at=init_data["updated_at"],
            )
            responses.append(response)
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to list initiatives: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list initiatives: {str(e)}"
        )


@router.get("/{initiative_id}", response_model=InitiativeResponse)
async def get_initiative(
    initiative_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Get detailed information about an initiative"""
    
    try:
        status_data = orchestrator.get_initiative_status(initiative_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Initiative not found"
            )
        
        init_data = status_data["initiative"]
        
        response = InitiativeResponse(
            id=init_data["id"],
            title=init_data["title"], 
            goal=init_data["goal"],
            status=init_data["status"],
            plan_id=init_data["plan_id"],
            owner=init_data["owner"],
            org_id=init_data["org_id"],
            jira_key=init_data.get("jira_key"),
            created_at=init_data["created_at"],
            updated_at=init_data["updated_at"],
            progress=status_data.get("progress"),
            execution_status=status_data.get("execution_status"),
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get initiative {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get initiative: {str(e)}"
        )


@router.post("/{initiative_id}/execute")
async def execute_initiative(
    initiative_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Start executing an initiative"""
    
    try:
        # Start execution in background
        background_tasks.add_task(
            orchestrator.execute_initiative,
            initiative_id
        )
        
        return {
            "initiative_id": initiative_id,
            "message": "Initiative execution started",
            "status": "executing"
        }
        
    except Exception as e:
        logger.error(f"Failed to start execution for {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start execution: {str(e)}"
        )


@router.post("/{initiative_id}/pause")
async def pause_initiative(
    initiative_id: str,
    reason: str = "Manual pause",
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Pause an executing initiative"""
    
    try:
        success = await orchestrator.pause_initiative(initiative_id, reason)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Initiative cannot be paused (not found or not executing)"
            )
        
        return {
            "initiative_id": initiative_id,
            "message": "Initiative paused",
            "reason": reason,
            "status": "paused"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause initiative {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause initiative: {str(e)}"
        )


@router.post("/{initiative_id}/resume")
async def resume_initiative(
    initiative_id: str,
    checkpoint_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Resume a paused initiative"""
    
    try:
        success = await orchestrator.resume_initiative(initiative_id, checkpoint_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Initiative cannot be resumed (not found or not paused)"
            )
        
        return {
            "initiative_id": initiative_id,
            "message": "Initiative resumed",
            "checkpoint_id": checkpoint_id,
            "status": "executing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume initiative {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume initiative: {str(e)}"
        )


@router.get("/{initiative_id}/checkpoints", response_model=List[CheckpointResponse])
async def list_checkpoints(
    initiative_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List checkpoints for an initiative"""
    
    try:
        checkpoint_engine = CheckpointEngine(db)
        checkpoints = checkpoint_engine.list_checkpoints(
            initiative_id=initiative_id,
            limit=limit
        )
        
        responses = []
        for checkpoint in checkpoints:
            response = CheckpointResponse(
                checkpoint_id=checkpoint.checkpoint_id,
                initiative_id=checkpoint.initiative_id,
                checkpoint_type=checkpoint.checkpoint_type.value,
                created_at=checkpoint.created_at.isoformat(),
                created_by=checkpoint.created_by,
                description=checkpoint.description,
                tags=checkpoint.tags,
                progress_summary=checkpoint.progress_summary,
            )
            responses.append(response)
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to list checkpoints for {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list checkpoints: {str(e)}"
        )


@router.post("/{initiative_id}/replan")
async def request_replan(
    initiative_id: str,
    request: ReplanRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Request replanning for an initiative"""
    
    try:
        # Get initiative status
        status_data = orchestrator.get_initiative_status(initiative_id)
        if not status_data or not status_data["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Initiative not found or not active"
            )
        
        # This would trigger replanning in the orchestrator
        # For now, return success response
        return {
            "initiative_id": initiative_id,
            "message": "Replan request submitted",
            "trigger": request.trigger,
            "scope": request.scope,
            "status": "replan_requested"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to request replan for {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to request replan: {str(e)}"
        )


@router.get("/{initiative_id}/progress/stream")
async def stream_initiative_progress(
    initiative_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    orchestrator: LongHorizonOrchestrator = Depends(get_orchestrator)
):
    """Stream real-time progress updates for an initiative"""
    
    async def event_generator():
        """Generate Server-Sent Events for initiative progress"""
        
        # Send initial status
        status_data = orchestrator.get_initiative_status(initiative_id)
        if status_data:
            yield f"data: {json.dumps(status_data)}\n\n"
        
        # Stream ongoing updates (simplified implementation)
        # In production, this would connect to the actual event stream
        datetime.now()
        
        while True:
            await asyncio.sleep(5)  # Poll every 5 seconds
            
            # Check if still active
            current_status = orchestrator.get_initiative_status(initiative_id)
            if not current_status or not current_status.get("is_active"):
                break
            
            # Send progress update
            progress_data = {
                "timestamp": datetime.now().isoformat(),
                "initiative_id": initiative_id,
                "progress": current_status.get("progress", {}),
                "execution_status": current_status.get("execution_status", {}),
            }
            
            yield f"data: {json.dumps(progress_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/{initiative_id}/analytics")
async def get_initiative_analytics(
    initiative_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get analytics and insights for an initiative"""
    
    try:
        # Get various analytics
        checkpoint_engine = CheckpointEngine(db)
        adaptive_replanner = AdaptiveReplanner()
        
        checkpoint_analytics = checkpoint_engine.get_checkpoint_analytics(initiative_id)
        replan_analytics = adaptive_replanner.get_replan_analytics(initiative_id)
        
        analytics = {
            "initiative_id": initiative_id,
            "checkpoint_analytics": checkpoint_analytics,
            "replan_analytics": replan_analytics,
            "generated_at": datetime.now().isoformat(),
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"Failed to get analytics for {initiative_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for Phase 4.9 services"""
    
    return {
        "status": "healthy",
        "phase": "4.9",
        "capabilities": [
            "initiative_management",
            "long_horizon_execution", 
            "autonomous_planning",
            "checkpoint_recovery",
            "adaptive_replanning"
        ],
        "timestamp": datetime.now().isoformat(),
    }
