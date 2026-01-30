"""
Enterprise Project Database Models.

Persistent storage for enterprise-level projects that span weeks/months.
Tracks project state, goals, architecture decisions, and human checkpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from backend.core.db import Base


class EnterpriseProject(Base):
    """
    Enterprise project tracking for long-running development efforts.

    Stores project state, goals, milestones, architecture decisions,
    and coordinates with the task queue and human checkpoints.
    """

    __tablename__ = "enterprise_projects"

    # Primary key
    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_session_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_workspace_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    initiative_id: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="Link to long-horizon initiative if using orchestrator",
    )

    # Project metadata
    name: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Project display name",
    )
    description: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Project description and objectives",
    )
    project_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        default="general",
        comment="Type: e-commerce, microservices, api, monolith, etc.",
    )

    # Goals and milestones
    goals: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Project goals: [{id, description, status, due_date}]",
    )
    milestones: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Milestones: [{id, name, tasks, completed_at}]",
    )

    # Progress tracking
    completed_components: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Completed: [{component, files, tests, verified_at}]",
    )
    pending_components: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Pending: [{component, dependencies, estimated_hours}]",
    )

    # Architecture decisions (ADRs)
    architecture_decisions: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="ADRs: [{id, title, context, decision, consequences, date}]",
    )

    # Human input tracking
    blockers: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Blockers: [{id, description, requires_input, resolved_at}]",
    )
    human_decisions: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Decisions: [{decision_id, question, options, chosen, reason, timestamp}]",
    )

    # Project configuration
    config: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default=dict,
        comment="Project-specific configuration and settings",
    )

    # Status tracking
    status: Mapped[str] = Column(
        String(20),
        nullable=False,
        default="planning",
        comment="Status: planning, active, paused, blocked, completed, failed",
    )
    progress_percentage: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Overall progress 0-100",
    )

    # Iteration tracking
    total_iterations: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total iterations executed across all sessions",
    )
    last_checkpoint_iteration: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Iteration number of last checkpoint",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_active_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time work was done on this project",
    )
    completed_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When project was marked complete",
    )

    # Relationships
    tasks = relationship(
        "ProjectTaskQueue",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    checkpoint_gates = relationship(
        "HumanCheckpointGate",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_enterprise_project_user_status", "user_id", "status"),
        Index("idx_enterprise_project_workspace", "workspace_session_id"),
        Index("idx_enterprise_project_updated", "updated_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "workspace_session_id": (
                str(self.workspace_session_id) if self.workspace_session_id else None
            ),
            "initiative_id": self.initiative_id,
            "name": self.name,
            "description": self.description,
            "project_type": self.project_type,
            "goals": self.goals or [],
            "milestones": self.milestones or [],
            "completed_components": self.completed_components or [],
            "pending_components": self.pending_components or [],
            "architecture_decisions": self.architecture_decisions or [],
            "blockers": self.blockers or [],
            "human_decisions": self.human_decisions or [],
            "config": self.config or {},
            "status": self.status,
            "progress_percentage": self.progress_percentage,
            "total_iterations": self.total_iterations,
            "last_checkpoint_iteration": self.last_checkpoint_iteration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_active_at": (
                self.last_active_at.isoformat() if self.last_active_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class HumanCheckpointGate(Base):
    """
    Human approval gates that pause autonomous execution.

    Used for critical decisions like architecture review, security review,
    cost approval, and deployment approval.
    """

    __tablename__ = "human_checkpoint_gates"

    # Primary key
    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    project_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("enterprise_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        ForeignKey("project_task_queue.id", ondelete="SET NULL"),
        nullable=True,
        comment="Task that triggered this gate",
    )

    # Gate configuration
    gate_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: architecture_review, security_review, cost_approval, deployment_approval, milestone_review, custom",
    )
    title: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Human-readable title for the decision",
    )
    description: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Detailed description of what needs to be decided",
    )

    # Context that triggered this gate
    trigger_context: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default=dict,
        comment="Context: {task_id, step_id, reason, relevant_files}",
    )

    # Options presented to human
    options: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Options: [{id, label, description, trade_offs, recommended, estimated_impact}]",
    )

    # Decision
    status: Mapped[str] = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="Status: pending, approved, rejected, deferred",
    )
    chosen_option_id: Mapped[Optional[str]] = Column(
        String(100),
        nullable=True,
        comment="ID of the chosen option",
    )
    decision_reason: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Human's reasoning for the decision",
    )
    decided_by: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="User who made the decision",
    )
    decided_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notification tracking
    notification_sent: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether notification was sent to user",
    )
    reminder_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of reminders sent",
    )
    last_reminder_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Priority and urgency
    priority: Mapped[str] = Column(
        String(20),
        nullable=False,
        default="normal",
        comment="Priority: low, normal, high, critical",
    )
    blocks_progress: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this gate blocks further execution",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this gate expires (auto-reject/defer)",
    )

    # Relationships
    project = relationship(
        "EnterpriseProject",
        back_populates="checkpoint_gates",
    )

    # Indexes
    __table_args__ = (
        Index("idx_checkpoint_gate_project_status", "project_id", "status"),
        Index("idx_checkpoint_gate_pending", "status", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "task_id": str(self.task_id) if self.task_id else None,
            "gate_type": self.gate_type,
            "title": self.title,
            "description": self.description,
            "trigger_context": self.trigger_context or {},
            "options": self.options or [],
            "status": self.status,
            "chosen_option_id": self.chosen_option_id,
            "decision_reason": self.decision_reason,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "priority": self.priority,
            "blocks_progress": self.blocks_progress,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class ProjectTaskQueue(Base):
    """
    Persistent task queue for enterprise projects.

    Supports 200+ tasks with dependencies, parallel execution marking,
    and verification criteria.
    """

    __tablename__ = "project_task_queue"

    # Primary key
    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    project_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("enterprise_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_task_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        ForeignKey("project_task_queue.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent task for hierarchical organization",
    )

    # Task identification
    task_key: Mapped[str] = Column(
        String(100),
        nullable=False,
        comment="Unique key within project (e.g., auth-001, db-migrate-002)",
    )
    milestone_id: Mapped[Optional[str]] = Column(
        String(100),
        nullable=True,
        comment="Associated milestone ID",
    )

    # Task definition
    title: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Human-readable task title",
    )
    description: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Detailed task description",
    )
    task_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        default="development",
        comment="Type: development, testing, deployment, documentation, infrastructure, review",
    )

    # Execution control
    priority: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=50,
        comment="Priority 1-100 (higher = more urgent)",
    )
    dependencies: Mapped[Optional[List[str]]] = Column(
        JSONB,
        default=list,
        comment="List of task_keys that must complete first",
    )
    can_parallelize: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this task can run in parallel with others",
    )
    estimated_minutes: Mapped[Optional[int]] = Column(
        Integer,
        nullable=True,
        comment="Estimated time to complete",
    )

    # Status and progress
    status: Mapped[str] = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="Status: pending, ready, in_progress, blocked, completed, failed, skipped",
    )
    progress_percentage: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Task progress 0-100",
    )
    blocked_reason: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Why this task is blocked",
    )

    # Execution details
    assigned_agent_id: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="ID of agent working on this task",
    )
    started_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Verification
    verification_criteria: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Criteria: [{type, command, expected_outcome}]",
    )
    verification_result: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        nullable=True,
        comment="Result of running verification",
    )
    verification_passed: Mapped[Optional[bool]] = Column(
        Boolean,
        nullable=True,
        comment="Whether verification passed",
    )

    # Error handling
    error_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of failed attempts",
    )
    last_error: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Last error message",
    )
    max_retries: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum retry attempts",
    )

    # Output artifacts
    outputs: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=list,
        comment="Outputs: [{type, path, description}]",
    )
    modified_files: Mapped[Optional[List[str]]] = Column(
        JSONB,
        default=list,
        comment="List of files modified by this task",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    project = relationship(
        "EnterpriseProject",
        back_populates="tasks",
    )
    subtasks = relationship(
        "ProjectTaskQueue",
        backref="parent_task",
        remote_side=[id],
    )

    # Indexes
    __table_args__ = (
        Index("idx_task_queue_project_status", "project_id", "status"),
        Index("idx_task_queue_project_priority", "project_id", "priority"),
        Index("idx_task_queue_key", "project_id", "task_key"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
            "task_key": self.task_key,
            "milestone_id": self.milestone_id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "priority": self.priority,
            "dependencies": self.dependencies or [],
            "can_parallelize": self.can_parallelize,
            "estimated_minutes": self.estimated_minutes,
            "status": self.status,
            "progress_percentage": self.progress_percentage,
            "blocked_reason": self.blocked_reason,
            "assigned_agent_id": self.assigned_agent_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "verification_criteria": self.verification_criteria or [],
            "verification_result": self.verification_result,
            "verification_passed": self.verification_passed,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "max_retries": self.max_retries,
            "outputs": self.outputs or [],
            "modified_files": self.modified_files or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_ready(self) -> bool:
        """Check if this task is ready to execute (dependencies satisfied)."""
        return self.status == "ready" or (
            self.status == "pending" and not self.dependencies
        )
