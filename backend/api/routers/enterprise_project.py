"""
Enterprise Project API Router.

REST API endpoints for managing enterprise-level projects.
Enables building full applications over weeks/months with:
- Project lifecycle management
- Task decomposition and tracking
- Human checkpoint gates for critical decisions
- Architecture decision records
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.auth.deps import get_current_user
from backend.services.enterprise_project_service import EnterpriseProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi/enterprise", tags=["enterprise-project"])


# =============================================================================
# Pydantic Models
# =============================================================================


class ProjectGoal(BaseModel):
    """A project goal."""

    id: str = Field(..., description="Unique goal ID")
    description: str = Field(..., description="Goal description")
    status: str = Field(default="pending", description="pending, in_progress, completed")


class ProjectMilestone(BaseModel):
    """A project milestone."""

    id: str = Field(..., description="Unique milestone ID")
    name: str = Field(..., description="Milestone name")
    description: Optional[str] = Field(None, description="Milestone description")
    target_date: Optional[str] = Field(None, description="Target completion date")
    task_keys: List[str] = Field(default_factory=list, description="Tasks in this milestone")


class CreateProjectRequest(BaseModel):
    """Request to create a new enterprise project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    project_type: str = Field(
        default="general",
        description="Project type: e-commerce, microservices, api, frontend, mobile, etc.",
    )
    workspace_session_id: Optional[str] = Field(None, description="Link to workspace session")
    goals: Optional[List[ProjectGoal]] = Field(None, description="Initial project goals")
    milestones: Optional[List[ProjectMilestone]] = Field(None, description="Initial milestones")
    config: Optional[Dict[str, Any]] = Field(None, description="Project configuration")


class UpdateProjectRequest(BaseModel):
    """Request to update a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: Optional[str] = None
    goals: Optional[List[Dict[str, Any]]] = None
    milestones: Optional[List[Dict[str, Any]]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, description="planning, active, paused, blocked, completed")
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)


class TaskVerificationCriteria(BaseModel):
    """Verification criteria for a task."""

    type: str = Field(..., description="test, lint, build, manual, etc.")
    command: Optional[str] = Field(None, description="Command to run for verification")
    expected_output: Optional[str] = Field(None, description="Expected output pattern")
    required: bool = Field(default=True, description="Whether this criteria must pass")


class CreateTaskRequest(BaseModel):
    """Request to create a task."""

    task_key: str = Field(..., min_length=1, max_length=100, description="Unique task key")
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    task_type: str = Field(
        default="development",
        description="development, testing, documentation, deployment, review, etc.",
    )
    priority: int = Field(default=50, ge=0, le=100, description="Task priority (0-100)")
    dependencies: Optional[List[str]] = Field(None, description="List of dependent task_keys")
    can_parallelize: bool = Field(default=False, description="Can run in parallel with others")
    verification_criteria: Optional[List[TaskVerificationCriteria]] = Field(
        None, description="How to verify task completion"
    )
    milestone_id: Optional[str] = Field(None, description="Associated milestone")
    parent_task_id: Optional[str] = Field(None, description="Parent task for sub-tasks")


class BulkCreateTasksRequest(BaseModel):
    """Request to create multiple tasks."""

    tasks: List[CreateTaskRequest] = Field(..., min_length=1, max_length=500)


class UpdateTaskRequest(BaseModel):
    """Request to update a task status."""

    status: str = Field(..., description="pending, ready, in_progress, completed, failed, skipped")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    verification_result: Optional[Dict[str, Any]] = Field(None, description="Verification results")
    outputs: Optional[List[Dict[str, Any]]] = Field(None, description="Task outputs/artifacts")
    modified_files: Optional[List[str]] = Field(None, description="Files modified by task")
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)


class GateOption(BaseModel):
    """An option for a checkpoint gate."""

    id: str = Field(..., description="Option ID")
    label: str = Field(..., description="Option label")
    description: str = Field(..., description="Detailed description")
    trade_offs: Optional[List[str]] = Field(None, description="Trade-offs for this option")
    recommended: bool = Field(default=False, description="Whether this is the recommended option")


class CreateGateRequest(BaseModel):
    """Request to create a human checkpoint gate."""

    gate_type: str = Field(
        ...,
        description="architecture_review, security_review, cost_approval, deployment_approval, milestone_review",
    )
    title: str = Field(..., min_length=1, max_length=255, description="Decision title")
    description: Optional[str] = Field(None, description="Detailed description")
    options: List[GateOption] = Field(..., min_length=2, max_length=10, description="Decision options")
    trigger_context: Optional[Dict[str, Any]] = Field(None, description="Context that triggered gate")
    task_id: Optional[str] = Field(None, description="Associated task")
    priority: str = Field(default="normal", description="low, normal, high, critical")
    blocks_progress: bool = Field(default=True, description="Whether this blocks execution")


class ProcessGateDecisionRequest(BaseModel):
    """Request to process a gate decision."""

    chosen_option_id: str = Field(..., description="ID of the chosen option")
    decision_reason: Optional[str] = Field(None, description="Reason for the decision")


class CreateADRRequest(BaseModel):
    """Request to create an Architecture Decision Record."""

    title: str = Field(..., min_length=1, max_length=255, description="ADR title")
    context: str = Field(..., description="Context and problem statement")
    decision: str = Field(..., description="The decision made")
    consequences: List[str] = Field(..., min_length=1, description="Consequences of the decision")
    alternatives: Optional[List[Dict[str, str]]] = Field(
        None, description="Alternatives considered: [{option, reason_rejected}]"
    )
    status: str = Field(
        default="accepted", description="proposed, accepted, deprecated, superseded"
    )


class ProjectResponse(BaseModel):
    """Response containing project details."""

    id: str
    user_id: int
    name: str
    description: Optional[str]
    project_type: str
    status: str
    progress_percentage: int
    total_iterations: int
    goals: List[Dict[str, Any]]
    milestones: List[Dict[str, Any]]
    architecture_decisions: List[Dict[str, Any]]
    completed_components: List[Dict[str, Any]]
    pending_components: List[Dict[str, Any]]
    blockers: List[Dict[str, Any]]
    config: Dict[str, Any]
    created_at: str
    updated_at: str
    last_active_at: Optional[str]


class TaskResponse(BaseModel):
    """Response containing task details."""

    id: str
    project_id: str
    task_key: str
    title: str
    description: Optional[str]
    task_type: str
    priority: int
    status: str
    dependencies: List[str]
    can_parallelize: bool
    verification_criteria: List[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    verification_passed: bool
    outputs: List[Dict[str, Any]]
    modified_files: List[str]
    milestone_id: Optional[str]
    error_count: int
    last_error: Optional[str]
    progress_percentage: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class GateResponse(BaseModel):
    """Response containing gate details."""

    id: str
    project_id: str
    gate_type: str
    title: str
    description: Optional[str]
    options: List[Dict[str, Any]]
    status: str
    chosen_option_id: Optional[str]
    decision_reason: Optional[str]
    decided_by: Optional[str]
    decided_at: Optional[str]
    priority: str
    blocks_progress: bool
    created_at: str


# =============================================================================
# Helper Functions
# =============================================================================


def _project_to_response(project) -> ProjectResponse:
    """Convert project model to response."""
    return ProjectResponse(
        id=str(project.id),
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        status=project.status,
        progress_percentage=project.progress_percentage,
        total_iterations=project.total_iterations,
        goals=project.goals or [],
        milestones=project.milestones or [],
        architecture_decisions=project.architecture_decisions or [],
        completed_components=project.completed_components or [],
        pending_components=project.pending_components or [],
        blockers=project.blockers or [],
        config=project.config or {},
        created_at=project.created_at.isoformat() if project.created_at else "",
        updated_at=project.updated_at.isoformat() if project.updated_at else "",
        last_active_at=project.last_active_at.isoformat() if project.last_active_at else None,
    )


def _task_to_response(task) -> TaskResponse:
    """Convert task model to response."""
    return TaskResponse(
        id=str(task.id),
        project_id=str(task.project_id),
        task_key=task.task_key,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        priority=task.priority,
        status=task.status,
        dependencies=task.dependencies or [],
        can_parallelize=task.can_parallelize,
        verification_criteria=task.verification_criteria or [],
        verification_result=task.verification_result,
        verification_passed=task.verification_passed,
        outputs=task.outputs or [],
        modified_files=task.modified_files or [],
        milestone_id=task.milestone_id,
        error_count=task.error_count,
        last_error=task.last_error,
        progress_percentage=task.progress_percentage,
        created_at=task.created_at.isoformat() if task.created_at else "",
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


def _gate_to_response(gate) -> GateResponse:
    """Convert gate model to response."""
    return GateResponse(
        id=str(gate.id),
        project_id=str(gate.project_id),
        gate_type=gate.gate_type,
        title=gate.title,
        description=gate.description,
        options=gate.options or [],
        status=gate.status,
        chosen_option_id=gate.chosen_option_id,
        decision_reason=gate.decision_reason,
        decided_by=gate.decided_by,
        decided_at=gate.decided_at.isoformat() if gate.decided_at else None,
        priority=gate.priority,
        blocks_progress=gate.blocks_progress,
        created_at=gate.created_at.isoformat() if gate.created_at else "",
    )


# =============================================================================
# Project Lifecycle Endpoints
# =============================================================================


@router.post("/projects", response_model=ProjectResponse)
def create_project(
    request: CreateProjectRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Create a new enterprise project.

    Enterprise projects support long-running development spanning weeks/months.
    """
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    project = service.create_project(
        user_id=user_id,
        name=request.name,
        description=request.description,
        project_type=request.project_type,
        workspace_session_id=request.workspace_session_id,
        goals=[g.model_dump() for g in request.goals] if request.goals else None,
        config=request.config,
    )

    # Add milestones if provided
    if request.milestones:
        service.update_project(
            str(project.id),
            user_id,
            {"milestones": [m.model_dump() for m in request.milestones]},
        )
        db.refresh(project)

    logger.info(
        "Created enterprise project via API",
        extra={"project_id": str(project.id), "user_id": user_id},
    )

    return _project_to_response(project)


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max projects to return"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all enterprise projects for the current user."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)
    projects = service.get_user_projects(user_id, status=status, limit=limit)

    return [_project_to_response(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get an enterprise project by ID."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)
    project = service.get_project(project_id, user_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return _project_to_response(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update an enterprise project."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    updates = request.model_dump(exclude_unset=True)
    project = service.update_project(project_id, user_id, updates)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return _project_to_response(project)


@router.post("/projects/{project_id}/start", response_model=ProjectResponse)
def start_project(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Start or resume project execution."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)
    project = service.update_project_status(project_id, user_id, "active")

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("Started project execution", extra={"project_id": project_id})
    return _project_to_response(project)


@router.post("/projects/{project_id}/pause", response_model=ProjectResponse)
def pause_project(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Pause project execution."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)
    project = service.update_project_status(project_id, user_id, "paused")

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("Paused project execution", extra={"project_id": project_id})
    return _project_to_response(project)


@router.get("/projects/{project_id}/context")
def get_project_context(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get the memory context for a project (for agent injection)."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)
    context = service.get_project_memory_context(project_id, user_id)

    if not context:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"project_id": project_id, "context": context}


# =============================================================================
# Task Management Endpoints
# =============================================================================


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse)
def create_task(
    project_id: str,
    request: CreateTaskRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Add a task to the project queue."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = service.add_task(
        project_id=project_id,
        task_key=request.task_key,
        title=request.title,
        description=request.description,
        task_type=request.task_type,
        priority=request.priority,
        dependencies=request.dependencies,
        can_parallelize=request.can_parallelize,
        verification_criteria=[v.model_dump() for v in request.verification_criteria]
        if request.verification_criteria
        else None,
        milestone_id=request.milestone_id,
        parent_task_id=request.parent_task_id,
    )

    return _task_to_response(task)


@router.post("/projects/{project_id}/tasks/bulk", response_model=List[TaskResponse])
def create_tasks_bulk(
    project_id: str,
    request: BulkCreateTasksRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Add multiple tasks to the project queue."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks_data = [
        {
            "task_key": t.task_key,
            "title": t.title,
            "description": t.description,
            "task_type": t.task_type,
            "priority": t.priority,
            "dependencies": t.dependencies or [],
            "can_parallelize": t.can_parallelize,
            "verification_criteria": [v.model_dump() for v in t.verification_criteria]
            if t.verification_criteria
            else [],
            "milestone_id": t.milestone_id,
        }
        for t in request.tasks
    ]

    tasks = service.add_tasks_bulk(project_id, tasks_data)

    logger.info(
        "Created bulk tasks",
        extra={"project_id": project_id, "count": len(tasks)},
    )

    return [_task_to_response(t) for t in tasks]


@router.get("/projects/{project_id}/tasks", response_model=List[TaskResponse])
def list_tasks(
    project_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all tasks for a project."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = service.get_project_tasks(project_id, status=status, task_type=task_type)

    return [_task_to_response(t) for t in tasks]


@router.get("/projects/{project_id}/tasks/ready", response_model=List[TaskResponse])
def get_ready_tasks(
    project_id: str,
    max_tasks: int = Query(5, ge=1, le=20, description="Max tasks to return"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get tasks that are ready for execution (dependencies satisfied)."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = service.get_ready_tasks(project_id, max_tasks=max_tasks)

    return [_task_to_response(t) for t in tasks]


@router.patch("/projects/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    project_id: str,
    task_id: str,
    request: UpdateTaskRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update a task's status."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = service.update_task_status(
        task_id=task_id,
        status=request.status,
        error_message=request.error_message,
        verification_result=request.verification_result,
        outputs=request.outputs,
        modified_files=request.modified_files,
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return _task_to_response(task)


# =============================================================================
# Human Checkpoint Gate Endpoints
# =============================================================================


@router.get("/gates/pending", response_model=List[GateResponse])
def list_all_pending_gates(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get all pending checkpoint gates across all projects for the current user."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Get all user's projects
    projects = service.get_user_projects(user_id, status=None, limit=100)

    all_gates = []
    for project in projects:
        gates = service.get_pending_gates(str(project.id))
        for gate in gates:
            # Add project name to gate for display
            gate_response = _gate_to_response(gate)
            gate_response_dict = gate_response.model_dump()
            gate_response_dict["project_name"] = project.name
            all_gates.append(gate_response_dict)

    # Sort by priority (critical > high > normal > low) and then by created_at
    priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    all_gates.sort(
        key=lambda g: (
            not g.get("blocks_progress", True),  # Blocking gates first
            priority_order.get(g.get("priority", "normal"), 2),
            g.get("created_at", ""),
        )
    )

    return all_gates


@router.get("/projects/{project_id}/gates", response_model=List[GateResponse])
def list_pending_gates(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get all pending checkpoint gates for a project."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    gates = service.get_pending_gates(project_id)

    return [_gate_to_response(g) for g in gates]


@router.post("/projects/{project_id}/gates", response_model=GateResponse)
def create_gate(
    project_id: str,
    request: CreateGateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a human checkpoint gate."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    gate = service.create_checkpoint_gate(
        project_id=project_id,
        gate_type=request.gate_type,
        title=request.title,
        description=request.description,
        options=[o.model_dump() for o in request.options],
        trigger_context=request.trigger_context,
        task_id=request.task_id,
        priority=request.priority,
        blocks_progress=request.blocks_progress,
    )

    return _gate_to_response(gate)


@router.get("/projects/{project_id}/gates/{gate_id}", response_model=GateResponse)
def get_gate(
    project_id: str,
    gate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a specific checkpoint gate."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    gate = service.get_gate(gate_id)
    if not gate or str(gate.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Gate not found")

    return _gate_to_response(gate)


@router.post("/projects/{project_id}/gates/{gate_id}/decide", response_model=GateResponse)
def process_gate_decision(
    project_id: str,
    gate_id: str,
    request: ProcessGateDecisionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submit a decision for a checkpoint gate."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    # Verify project ownership
    project = service.get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify gate exists and belongs to project
    gate = service.get_gate(gate_id)
    if not gate or str(gate.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Gate not found")

    if gate.status != "pending":
        raise HTTPException(
            status_code=400, detail=f"Gate already processed with status: {gate.status}"
        )

    # Validate chosen option exists
    option_ids = [opt.get("id") for opt in (gate.options or [])]
    if request.chosen_option_id not in option_ids:
        raise HTTPException(status_code=400, detail="Invalid option ID")

    gate = service.process_gate_decision(
        gate_id=gate_id,
        chosen_option_id=request.chosen_option_id,
        decision_reason=request.decision_reason,
        decided_by=str(user_id),
    )

    logger.info(
        "Processed gate decision via API",
        extra={
            "gate_id": gate_id,
            "chosen_option_id": request.chosen_option_id,
            "user_id": user_id,
        },
    )

    return _gate_to_response(gate)


# =============================================================================
# Architecture Decision Records Endpoints
# =============================================================================


@router.post("/projects/{project_id}/adrs", response_model=ProjectResponse)
def create_adr(
    project_id: str,
    request: CreateADRRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Add an Architecture Decision Record to the project."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)

    project = service.add_architecture_decision(
        project_id=project_id,
        user_id=user_id,
        title=request.title,
        context=request.context,
        decision=request.decision,
        consequences=request.consequences,
        alternatives=request.alternatives,
        status=request.status,
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info(
        "Created ADR via API",
        extra={"project_id": project_id, "adr_title": request.title},
    )

    return _project_to_response(project)


@router.get("/projects/{project_id}/adrs")
def list_adrs(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all Architecture Decision Records for a project."""
    user_id = getattr(user, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = EnterpriseProjectService(db)
    project = service.get_project(project_id, user_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project_id,
        "adrs": project.architecture_decisions or [],
    }
