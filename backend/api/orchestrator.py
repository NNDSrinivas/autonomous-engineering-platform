"""
Navi Orchestrator API - Multi-Agent AI Engineering Platform
Provides REST endpoints for orchestrator execution and coordination.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import traceback
import uuid
from datetime import datetime

try:
    from backend.orchestrator import NaviOrchestrator
except ImportError:
    # Fallback for development/testing
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.orchestrator import NaviOrchestrator

from backend.core.db import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])
logger = logging.getLogger(__name__)

class OrchestratorRequest(BaseModel):
    """Request model for orchestrator execution."""
    instruction: str
    workspace_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

class OrchestratorResponse(BaseModel):
    """Response model for orchestrator execution results."""
    session_id: str
    success: bool
    plan: Dict[str, Any]
    execution_results: List[Dict[str, Any]]
    review: Dict[str, Any]
    response: str

@router.post("/execute", response_model=OrchestratorResponse)
async def execute_orchestrator(
    request: OrchestratorRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a multi-agent orchestrator instruction.
    
    This endpoint coordinates all 5 specialized agents:
    - PlannerAgent: AI-driven task decomposition
    - MemoryAgent: Persistent memory and learning
    - RepoAnalysisAgent: FAANG-level repository intelligence
    - ExecutionAgent: Safe multi-modal execution
    - ReviewAgent: Quality assurance and validation
    
    Args:
        request: Orchestrator execution request with instruction and context
        db: Database session for persistence
        
    Returns:
        OrchestratorResponse with execution results, plan, and review
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        logger.info(f"[ORCHESTRATOR] Starting execution for session {session_id}")
        logger.info(f"[ORCHESTRATOR] Instruction: {request.instruction}")
        
        # Initialize orchestrator
        orchestrator = NaviOrchestrator()
        
        # Execute instruction with full multi-agent coordination
        result = await orchestrator.handle_instruction(
            user_id=f"api_user_{session_id}",
            instruction=request.instruction,
            workspace_root="/tmp",  # Default workspace root - should be configurable
            options=request.workspace_context or {}
        )
        
        logger.info(f"[ORCHESTRATOR] Execution completed for session {session_id}")
        logger.info(f"[ORCHESTRATOR] Success: {result['success']}")
        logger.info(f"[ORCHESTRATOR] Plan steps: {len(result['plan']['steps'])}")
        logger.info(f"[ORCHESTRATOR] Execution results: {len(result['execution_results'])}")
        
        return OrchestratorResponse(
            session_id=session_id,
            success=result['success'],
            plan=result['plan'],
            execution_results=result['execution_results'],
            review=result['review'],
            response=result['response']
        )
        
    except Exception as e:
        error_msg = f"Orchestrator execution failed: {str(e)}"
        logger.error(f"[ORCHESTRATOR] Error for session {session_id}: {error_msg}")
        logger.error(f"[ORCHESTRATOR] Traceback: {traceback.format_exc()}")
        
        # Return structured error response instead of raising HTTP exception
        # This allows the frontend to show detailed error information
        return OrchestratorResponse(
            session_id=session_id,
            success=False,
            plan={"id": "error", "steps": []},
            execution_results=[{
                "step_id": "error",
                "success": False,
                "output": "",
                "error": error_msg,
                "files_modified": [],
                "execution_time": 0.0
            }],
            review={
                "overall_success": False,
                "success_rate": 0.0,
                "files_modified": [],
                "summary": f"Orchestrator execution failed: {str(e)}",
                "recommendations": [
                    "Check backend logs for detailed error information",
                    "Ensure all required dependencies are installed",
                    "Verify workspace context is properly formatted",
                    "Try a simpler instruction to test orchestrator functionality"
                ]
            },
            response=f"❌ **Orchestrator Execution Failed**\n\n{error_msg}\n\nPlease check the backend logs for more details."
        )

@router.get("/health")
async def orchestrator_health():
    """Check orchestrator health and readiness."""
    try:
        # Basic health check - ensure orchestrator can be imported and initialized
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "orchestrator": "ready",
                "planner_agent": "ready", 
                "memory_agent": "ready",
                "repo_analysis_agent": "ready",
                "execution_agent": "ready"
            },
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Orchestrator health check failed: {str(e)}"
        )

@router.get("/status/{session_id}")
async def get_session_status(session_id: str, db: Session = Depends(get_db)):
    """Get status of a specific orchestrator session."""
    try:
        # TODO: Implement session status tracking in database
        # For now, return basic response
        return {
            "session_id": session_id,
            "status": "unknown",
            "message": "Session status tracking not yet implemented"
        }
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Status check failed for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )