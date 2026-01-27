"""
Task Checkpoint Database Models.

Stores task execution state for recovery after interruptions.
Enables:
- Resume interrupted tasks without losing progress
- Cross-device session continuity
- Task execution analytics and debugging

All models support multi-tenancy via user_id.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped

from backend.core.db import Base


class TaskCheckpoint(Base):
    """
    Task checkpoint - stores state for resuming interrupted tasks.

    Captures the full state of a task execution including:
    - Original user request
    - Progress through execution steps
    - Files modified and commands run
    - Partial response content
    - Error/interruption details
    """

    __tablename__ = "task_checkpoints"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Session identification
    session_id: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Frontend session ID for this checkpoint",
    )
    message_id: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Message ID associated with this task",
    )

    # Original request
    user_message: Mapped[str] = Column(
        Text,
        nullable=False,
        comment="The original user message that started this task",
    )

    # Workspace context
    workspace_path: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Path to the workspace where task is executing",
    )

    # Task status
    status: Mapped[str] = Column(
        String(20),
        default="running",
        nullable=False,
        comment="Status: running, interrupted, completed, failed",
    )

    # Progress tracking
    current_step_index: Mapped[int] = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Current step index in the execution plan",
    )
    total_steps: Mapped[int] = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of steps in the plan",
    )
    steps: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=[],
        comment="List of step objects with id, title, status, completedAt",
    )

    # What was done
    modified_files: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=[],
        comment="Files modified: [{path, operation, timestamp, success}]",
    )
    executed_commands: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=[],
        comment="Commands run: [{command, exitCode, timestamp, success}]",
    )

    # Partial response content
    partial_content: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Partial response content accumulated before interruption",
    )

    # Streaming state (activities, narratives, thinking)
    streaming_state: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Streaming state: {activities, narratives, thinking}",
    )

    # Error/interruption info
    interrupted_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the task was interrupted",
    )
    interrupt_reason: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Reason for interruption",
    )

    # Retry tracking
    retry_count: Mapped[int] = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of retry attempts",
    )
    last_retry_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the last retry was attempted",
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

    # Expiry - checkpoints older than this should be cleaned up
    expires_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this checkpoint should be auto-deleted",
    )

    __table_args__ = (
        # Only one active checkpoint per user+session
        UniqueConstraint("user_id", "session_id", name="uq_checkpoint_user_session"),
        Index("idx_checkpoint_user_status", "user_id", "status"),
        Index("idx_checkpoint_session", "session_id"),
        Index("idx_checkpoint_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<TaskCheckpoint(id={self.id}, user_id={self.user_id}, status={self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "session_id": self.session_id,
            "message_id": self.message_id,
            "user_message": self.user_message,
            "workspace_path": self.workspace_path,
            "status": self.status,
            "current_step_index": self.current_step_index,
            "total_steps": self.total_steps,
            "steps": self.steps or [],
            "modified_files": self.modified_files or [],
            "executed_commands": self.executed_commands or [],
            "partial_content": self.partial_content,
            "streaming_state": self.streaming_state or {},
            "interrupted_at": self.interrupted_at.isoformat() if self.interrupted_at else None,
            "interrupt_reason": self.interrupt_reason,
            "retry_count": self.retry_count,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
