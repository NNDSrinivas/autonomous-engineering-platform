"""
Enhanced Autonomous Coding API - Cline-style step-by-step coding with enterprise intelligence

This API provides endpoints for:
1. Creating tasks from JIRA with full context
2. Step-by-step execution with user approval
3. Real-time progress tracking
4. Enterprise integration (Slack, Confluence, Zoom)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import logging

from backend.core.db import get_db
from backend.autonomous.enhanced_coding_engine import EnhancedAutonomousCodingEngine
from backend.core.ai.llm_service import LLMService
from backend.core.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/autonomous", tags=["autonomous-coding"])


class CreateTaskFromJiraRequest(BaseModel):
    jira_key: str
    user_context: Optional[Dict[str, Any]] = None


class ExecuteStepRequest(BaseModel):
    task_id: str
    step_id: str
    user_approved: bool
    user_feedback: Optional[str] = None


class TaskPresentationResponse(BaseModel):
    task: Dict[str, Any]
    context: Dict[str, Any]
    implementation_plan: Dict[str, Any]
    steps_preview: List[Dict[str, Any]]
    next_action: str


class StepExecutionResponse(BaseModel):
    status: str
    step: str
    file_path: Optional[str] = None
    changes_applied: bool = False
    validation: Optional[Dict[str, Any]] = None
    next_step: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Global engine instance (would be properly initialized in production)
_coding_engine: Optional[EnhancedAutonomousCodingEngine] = None


def get_coding_engine() -> EnhancedAutonomousCodingEngine:
    """Get or create the autonomous coding engine"""
    global _coding_engine
    if _coding_engine is None:
        # Initialize with proper dependencies
        llm_service = LLMService()
        vector_store = VectorStore()  # Placeholder
        workspace_path = "/workspace"  # Would be configurable

        _coding_engine = EnhancedAutonomousCodingEngine(
            llm_service=llm_service,
            vector_store=vector_store,
            workspace_path=workspace_path,
        )

    return _coding_engine


@router.post("/create-from-jira", response_model=TaskPresentationResponse)
async def create_task_from_jira(
    request: CreateTaskFromJiraRequest, db: Session = Depends(get_db)
):
    """
    Create autonomous coding task from JIRA ticket with full enterprise context

    This is where AEP excels over Cline - complete enterprise intelligence:
    - JIRA ticket details and context
    - Related Confluence documentation
    - Slack/Teams meeting discussions
    - Codebase analysis for related files
    - Team member context and preferences
    """
    try:
        engine = get_coding_engine()

        # Create task with full enterprise context
        task = await engine.create_task_from_jira(
            jira_key=request.jira_key, user_context=request.user_context or {}
        )

        # Generate comprehensive presentation for user
        presentation = await engine.present_task_to_user(task.id)

        logger.info(f"Created autonomous task from JIRA {request.jira_key}: {task.id}")

        return TaskPresentationResponse(**presentation)

    except Exception as e:
        logger.error(f"Failed to create task from JIRA {request.jira_key}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create autonomous task: {str(e)}"
        )


@router.post("/execute-step", response_model=StepExecutionResponse)
async def execute_step(request: ExecuteStepRequest, db: Session = Depends(get_db)):
    """
    Execute individual coding step with user approval

    Core workflow that matches Cline's step-by-step approach:
    1. User sees exactly what will be changed
    2. User explicitly approves or rejects
    3. If approved, execute with safety measures
    4. Show results and next step preview
    5. Handle errors gracefully with rollback options
    """
    try:
        engine = get_coding_engine()

        # Execute step with user approval
        result = await engine.execute_step(
            task_id=request.task_id,
            step_id=request.step_id,
            user_approved=request.user_approved,
        )

        logger.info(
            f"Executed step {request.step_id} for task {request.task_id}: {result['status']}"
        )

        return StepExecutionResponse(**result)

    except ValueError as e:
        logger.warning(f"Invalid request for step execution: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to execute step {request.step_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute step: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Get current status of autonomous coding task"""
    try:
        engine = get_coding_engine()

        task = engine.active_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "current_step": task.current_step_index,
            "total_steps": len(task.steps),
            "jira_key": task.jira_key,
            "branch_name": task.branch_name,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    except Exception as e:
        logger.error(f"Failed to get task status {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/steps")
async def get_task_steps(task_id: str, db: Session = Depends(get_db)):
    """Get all steps for a task with their current status"""
    try:
        engine = get_coding_engine()

        task = engine.active_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        steps = []
        for step in task.steps:
            steps.append(
                {
                    "id": step.id,
                    "description": step.description,
                    "file_path": step.file_path,
                    "operation": step.operation,
                    "status": step.status.value,
                    "reasoning": step.reasoning,
                    "user_feedback": step.user_feedback,
                }
            )

        return {
            "task_id": task_id,
            "total_steps": len(steps),
            "current_step": task.current_step_index,
            "steps": steps,
        }

    except Exception as e:
        logger.error(f"Failed to get task steps {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/preview-step/{step_id}")
async def preview_step_changes(
    task_id: str, step_id: str, db: Session = Depends(get_db)
):
    """
    Preview what changes a step will make before user approval

    Critical for user trust - show exactly what will happen
    """
    try:
        engine = get_coding_engine()

        task = engine.active_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        step = next((s for s in task.steps if s.id == step_id), None)
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        # Generate preview of changes
        preview = {
            "step_id": step.id,
            "description": step.description,
            "file_path": step.file_path,
            "operation": step.operation,
            "content_preview": step.content_preview,
            "diff_preview": step.diff_preview,
            "reasoning": step.reasoning,
            "dependencies": step.dependencies,
            "estimated_impact": "Low",  # Would be calculated
            "safety_checks": [
                "Backup created",
                "Syntax validation",
                "Test compatibility",
            ],
        }

        return preview

    except Exception as e:
        logger.error(f"Failed to preview step {step_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/create-pr")
async def create_pull_request(task_id: str, db: Session = Depends(get_db)):
    """Create pull request for completed autonomous coding task"""
    try:
        engine = get_coding_engine()

        result = await engine.create_pull_request(
            task_id=task_id,
            repository="current",  # Would be configurable
            branch_name=None,  # Use task's branch
        )

        logger.info(f"Created PR for task {task_id}: {result.get('pr_url', 'unknown')}")

        return result

    except Exception as e:
        logger.error(f"Failed to create PR for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint for autonomous coding service"""
    try:
        engine = get_coding_engine()

        return {
            "status": "healthy",
            "active_tasks": len(engine.active_tasks),
            "queue_size": len(engine.task_queue),
            "workspace_path": str(engine.workspace_path),
            "git_available": engine.repo is not None,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@router.get("/user-daily-context")
async def get_user_daily_context(request: Request, db: Session = Depends(get_db)):
    """
    Get comprehensive daily context for user greeting

    This is the "killer feature" - enterprise intelligence for daily workflow:
    - JIRA tasks assigned to user
    - Recent Slack/Teams discussions about their tasks
    - Confluence docs related to current work
    - Meeting notes and decisions
    - Team member availability and context
    """
    try:
        # Get user identity (would use proper auth)
        user_id = request.headers.get("X-User-Id", "default-user")

        # Gather comprehensive daily context
        daily_context = {
            "user": {
                "id": user_id,
                "name": "Developer",  # Would fetch from directory
                "timezone": "UTC",
                "preferences": {},
            },
            "jira_tasks": await _fetch_user_jira_tasks(user_id),
            "recent_discussions": await _fetch_recent_discussions(user_id),
            "documentation_updates": await _fetch_doc_updates(user_id),
            "meeting_context": await _fetch_meeting_context(user_id),
            "team_activity": await _fetch_team_activity(user_id),
            "suggested_priorities": await _suggest_daily_priorities(user_id),
        }

        return daily_context

    except Exception as e:
        logger.error(f"Failed to get daily context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions for enterprise context gathering
async def _fetch_user_jira_tasks(user_id: str) -> List[Dict[str, Any]]:
    """Fetch user's assigned JIRA tasks with context"""
    # Would integrate with your existing JIRA service
    return [
        {
            "key": "ENG-123",
            "title": "Implement user authentication",
            "priority": "High",
            "status": "In Progress",
            "estimate": "5 story points",
            "sprint": "Sprint 24",
        }
    ]


async def _fetch_recent_discussions(user_id: str) -> List[Dict[str, Any]]:
    """Fetch recent Slack/Teams discussions about user's work"""
    # Would integrate with your existing Slack/Teams connectors
    return [
        {
            "source": "slack",
            "channel": "#engineering",
            "summary": "Discussion about authentication flow",
            "participants": ["alice", "bob"],
            "key_points": ["Use OAuth2", "Consider MFA"],
            "timestamp": "2024-01-15T10:30:00Z",
        }
    ]


async def _fetch_doc_updates(user_id: str) -> List[Dict[str, Any]]:
    """Fetch recent Confluence documentation updates"""
    # Would integrate with your existing Confluence connector
    return [
        {
            "title": "Authentication Architecture",
            "url": "https://confluence.company.com/auth-arch",
            "updated": "2024-01-14T15:00:00Z",
            "summary": "Updated OAuth2 implementation details",
        }
    ]


async def _fetch_meeting_context(user_id: str) -> List[Dict[str, Any]]:
    """Fetch recent meeting notes and decisions"""
    # Would integrate with your existing Zoom/Teams connectors
    return [
        {
            "title": "Sprint Planning - Sprint 24",
            "date": "2024-01-12T09:00:00Z",
            "decisions": ["Prioritize auth work", "Use new UI framework"],
            "action_items": ["ENG-123 assigned to user"],
        }
    ]


async def _fetch_team_activity(user_id: str) -> List[Dict[str, Any]]:
    """Fetch relevant team member activity"""
    # Would use your existing team activity APIs
    return [
        {
            "member": "alice",
            "activity": "Completed OAuth2 research",
            "relevance": "Related to your ENG-123 task",
        }
    ]


async def _suggest_daily_priorities(user_id: str) -> List[Dict[str, Any]]:
    """AI-powered daily priority suggestions"""
    # Would use your LLM service to analyze context and suggest priorities
    return [
        {
            "priority": 1,
            "task": "ENG-123",
            "reasoning": "High priority, blocking other work",
            "estimated_effort": "4 hours",
            "dependencies": [],
        }
    ]
