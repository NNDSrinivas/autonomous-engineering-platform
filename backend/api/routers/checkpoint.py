"""
Task Checkpoint API Router.

Provides REST endpoints for managing task checkpoints, enabling:
- Task recovery after interruptions
- Progress sync between frontend and backend
- Cross-device session continuity
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.services.checkpoint_service import CheckpointService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi/checkpoint", tags=["navi-checkpoint"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CheckpointStep(BaseModel):
    """Individual step in the task execution."""

    id: str
    title: str
    status: str = Field(default="pending", pattern="^(pending|completed|failed|skipped)$")
    completedAt: Optional[str] = None


class ModifiedFile(BaseModel):
    """File modified during task execution."""

    path: str
    operation: str
    timestamp: str
    success: bool = True


class ExecutedCommand(BaseModel):
    """Command executed during task execution."""

    command: str
    exitCode: Optional[int] = None
    timestamp: str
    success: bool = True


class CreateCheckpointRequest(BaseModel):
    """Request to create a new checkpoint."""

    session_id: str
    message_id: str
    user_message: str
    workspace_path: Optional[str] = None
    total_steps: int = 0


class UpdateProgressRequest(BaseModel):
    """Request to update checkpoint progress."""

    current_step_index: Optional[int] = None
    steps: Optional[List[CheckpointStep]] = None
    partial_content: Optional[str] = None
    streaming_state: Optional[Dict[str, Any]] = None


class AddFileRequest(BaseModel):
    """Request to add a modified file."""

    file_path: str
    operation: str
    success: bool = True


class AddCommandRequest(BaseModel):
    """Request to add an executed command."""

    command: str
    exit_code: Optional[int] = None
    success: bool = True


class MarkInterruptedRequest(BaseModel):
    """Request to mark checkpoint as interrupted."""

    reason: str = "Connection lost"


class SyncCheckpointRequest(BaseModel):
    """Request to sync checkpoint data from frontend."""

    messageId: str
    userMessage: str
    workspacePath: Optional[str] = None
    status: str = "running"
    currentStepIndex: int = 0
    totalSteps: int = 0
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    modifiedFiles: List[Dict[str, Any]] = Field(default_factory=list)
    executedCommands: List[Dict[str, Any]] = Field(default_factory=list)
    partialContent: Optional[str] = None
    streamingState: Optional[Dict[str, Any]] = None
    retryCount: int = 0
    interruptedAt: Optional[str] = None


class CheckpointResponse(BaseModel):
    """Response model for checkpoint."""

    id: str
    session_id: str
    message_id: str
    user_message: str
    workspace_path: Optional[str] = None
    status: str
    current_step_index: int
    total_steps: int
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    modified_files: List[Dict[str, Any]] = Field(default_factory=list)
    executed_commands: List[Dict[str, Any]] = Field(default_factory=list)
    partial_content: Optional[str] = None
    streaming_state: Optional[Dict[str, Any]] = None
    interrupted_at: Optional[str] = None
    interrupt_reason: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=CheckpointResponse)
async def create_checkpoint(
    user_id: int,
    request: CreateCheckpointRequest,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """
    Create a new checkpoint for a task.

    If a checkpoint already exists for this session, it will be updated.
    """
    service = CheckpointService(db)

    checkpoint = service.create_checkpoint(
        user_id=user_id,
        session_id=request.session_id,
        message_id=request.message_id,
        user_message=request.user_message,
        workspace_path=request.workspace_path,
        total_steps=request.total_steps,
    )

    return CheckpointResponse(**checkpoint.to_dict())


@router.get("", response_model=Optional[CheckpointResponse])
async def get_checkpoint(
    user_id: int,
    session_id: str,
    db: Session = Depends(get_db),
) -> Optional[CheckpointResponse]:
    """Get the checkpoint for a session."""
    service = CheckpointService(db)

    checkpoint = service.get_checkpoint(user_id, session_id)
    if not checkpoint:
        return None

    return CheckpointResponse(**checkpoint.to_dict())


@router.get("/{checkpoint_id}", response_model=CheckpointResponse)
async def get_checkpoint_by_id(
    checkpoint_id: str,
    user_id: int,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Get a checkpoint by ID."""
    service = CheckpointService(db)

    checkpoint = service.get_checkpoint_by_id(checkpoint_id, user_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.patch("/progress", response_model=CheckpointResponse)
async def update_progress(
    user_id: int,
    session_id: str,
    request: UpdateProgressRequest,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Update checkpoint progress."""
    service = CheckpointService(db)

    # Convert steps to dicts if needed
    steps_dicts = None
    if request.steps:
        steps_dicts = [s.model_dump() for s in request.steps]

    checkpoint = service.update_progress(
        user_id=user_id,
        session_id=session_id,
        current_step_index=request.current_step_index,
        steps=steps_dicts,
        partial_content=request.partial_content,
        streaming_state=request.streaming_state,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/file", response_model=CheckpointResponse)
async def add_modified_file(
    user_id: int,
    session_id: str,
    request: AddFileRequest,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Add a modified file to the checkpoint."""
    service = CheckpointService(db)

    checkpoint = service.add_modified_file(
        user_id=user_id,
        session_id=session_id,
        file_path=request.file_path,
        operation=request.operation,
        success=request.success,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/command", response_model=CheckpointResponse)
async def add_executed_command(
    user_id: int,
    session_id: str,
    request: AddCommandRequest,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Add an executed command to the checkpoint."""
    service = CheckpointService(db)

    checkpoint = service.add_executed_command(
        user_id=user_id,
        session_id=session_id,
        command=request.command,
        exit_code=request.exit_code,
        success=request.success,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/interrupt", response_model=CheckpointResponse)
async def mark_interrupted(
    user_id: int,
    session_id: str,
    request: MarkInterruptedRequest = MarkInterruptedRequest(),
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Mark a checkpoint as interrupted."""
    service = CheckpointService(db)

    checkpoint = service.mark_interrupted(
        user_id=user_id,
        session_id=session_id,
        reason=request.reason,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/complete", response_model=CheckpointResponse)
async def mark_completed(
    user_id: int,
    session_id: str,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Mark a checkpoint as completed."""
    service = CheckpointService(db)

    checkpoint = service.mark_completed(
        user_id=user_id,
        session_id=session_id,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/fail", response_model=CheckpointResponse)
async def mark_failed(
    user_id: int,
    session_id: str,
    reason: str = "Task failed",
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Mark a checkpoint as failed."""
    service = CheckpointService(db)

    checkpoint = service.mark_failed(
        user_id=user_id,
        session_id=session_id,
        reason=reason,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/retry", response_model=CheckpointResponse)
async def increment_retry(
    user_id: int,
    session_id: str,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """Increment retry count and reset status to running."""
    service = CheckpointService(db)

    checkpoint = service.increment_retry(
        user_id=user_id,
        session_id=session_id,
    )

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return CheckpointResponse(**checkpoint.to_dict())


@router.get("/interrupted/list", response_model=List[CheckpointResponse])
async def get_interrupted_checkpoints(
    user_id: int,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
) -> List[CheckpointResponse]:
    """Get all interrupted checkpoints for a user."""
    service = CheckpointService(db)

    checkpoints = service.get_interrupted_checkpoints(user_id, limit)

    return [CheckpointResponse(**cp.to_dict()) for cp in checkpoints]


@router.delete("")
async def delete_checkpoint(
    user_id: int,
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Delete a checkpoint."""
    service = CheckpointService(db)

    success = service.delete_checkpoint(user_id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return {"message": "Checkpoint deleted successfully"}


@router.post("/sync", response_model=CheckpointResponse)
async def sync_from_frontend(
    user_id: str,  # Accept string to support "default_user" and numeric IDs
    session_id: str,
    request: SyncCheckpointRequest,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    """
    Sync checkpoint data from frontend localStorage.

    This allows the frontend to push its checkpoint state to the backend
    for cross-device persistence.
    """
    # Convert string user_id to int for database storage
    # "default_user" maps to user_id 1, numeric strings are converted directly
    if user_id == "default_user":
        numeric_user_id = 1
    else:
        try:
            numeric_user_id = int(user_id)
        except ValueError:
            # For any other non-numeric string, use default user ID
            numeric_user_id = 1
            logger.warning(f"Unknown user_id '{user_id}', using default user_id=1")

    service = CheckpointService(db)

    checkpoint = service.sync_from_frontend(
        user_id=numeric_user_id,
        session_id=session_id,
        checkpoint_data=request.model_dump(),
    )

    return CheckpointResponse(**checkpoint.to_dict())


@router.post("/cleanup")
async def cleanup_expired(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Clean up expired checkpoints.

    This endpoint should be called periodically by a background job.
    """
    service = CheckpointService(db)

    count = service.cleanup_expired()

    return {"message": f"Cleaned up {count} expired checkpoints", "count": count}
