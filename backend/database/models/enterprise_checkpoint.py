"""
Enterprise Checkpoint Database Model.

Persistent storage for checkpoints that enable crash recovery for enterprise projects.
Stores complete agent state including conversation history, file changes, and execution context.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

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


class EnterpriseCheckpoint(Base):
    """
    Checkpoint storage for enterprise project crash recovery.

    Stores complete state snapshots that allow resuming execution
    from any point after crashes, restarts, or pauses.
    """

    __tablename__ = "enterprise_checkpoints"

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
        comment="Task being executed when checkpoint was created",
    )

    # Checkpoint metadata
    checkpoint_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        default="automatic",
        comment="Type: automatic, manual, pre_gate, error_recovery, milestone",
    )
    iteration_number: Mapped[int] = Column(
        Integer,
        nullable=False,
        comment="Iteration number when checkpoint was created",
    )
    checkpoint_reason: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Reason for creating this checkpoint",
    )

    # Execution state
    agent_state: Mapped[Dict[str, Any]] = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Complete agent state: {status, iteration, files_modified, etc.}",
    )
    conversation_history: Mapped[List[Dict[str, Any]]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Conversation history up to this point (summarized if large)",
    )
    tool_call_history: Mapped[List[Dict[str, Any]]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Tool calls made in this session",
    )

    # File state
    files_modified: Mapped[List[str]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of files modified since project start",
    )
    files_created: Mapped[List[str]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of files created since project start",
    )
    file_snapshots: Mapped[Optional[Dict[str, str]]] = Column(
        JSONB,
        nullable=True,
        comment="Snapshots of critical files at checkpoint time",
    )

    # Error state
    error_history: Mapped[List[Dict[str, Any]]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Errors encountered: [{type, message, iteration, resolved}]",
    )
    failed_approaches: Mapped[List[Dict[str, Any]]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Approaches that failed (for avoiding retries)",
    )

    # Task queue state
    completed_tasks: Mapped[List[str]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Task IDs completed at checkpoint time",
    )
    pending_tasks: Mapped[List[str]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Task IDs still pending",
    )
    current_task_progress: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        nullable=True,
        comment="Progress on current task if mid-execution",
    )

    # Context summary (for large histories)
    context_summary: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="LLM-generated summary of context for long-running projects",
    )
    is_context_summarized: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether conversation_history is summarized version",
    )

    # Verification state
    verification_results: Mapped[List[Dict[str, Any]]] = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="Results of verification runs: [{type, success, output}]",
    )

    # Metadata
    is_valid: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this checkpoint is valid for restoration",
    )
    invalidation_reason: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Why checkpoint was invalidated (if applicable)",
    )
    restored_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this checkpoint has been restored",
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
        comment="When this checkpoint expires (for cleanup)",
    )

    # Indexes
    __table_args__ = (
        Index("idx_checkpoint_project_iteration", "project_id", "iteration_number"),
        Index("idx_checkpoint_project_valid", "project_id", "is_valid"),
        Index("idx_checkpoint_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "task_id": str(self.task_id) if self.task_id else None,
            "checkpoint_type": self.checkpoint_type,
            "iteration_number": self.iteration_number,
            "checkpoint_reason": self.checkpoint_reason,
            "agent_state": self.agent_state or {},
            "conversation_history_length": len(self.conversation_history or []),
            "files_modified": self.files_modified or [],
            "files_created": self.files_created or [],
            "completed_tasks": self.completed_tasks or [],
            "pending_tasks": self.pending_tasks or [],
            "is_context_summarized": self.is_context_summarized,
            "is_valid": self.is_valid,
            "restored_count": self.restored_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
