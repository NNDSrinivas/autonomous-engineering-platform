"""
Task Checkpoint Service

Provides persistent checkpoint management for NAVI task execution.
Enables task recovery after interruptions by storing:
- Task progress state
- Files modified during execution
- Commands executed
- Partial response content
- Streaming state for resume

This service works with the frontend to sync checkpoint data
stored in localStorage with the database for cross-device persistence.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select, delete
from sqlalchemy.orm import Session

from backend.database.models import TaskCheckpoint

logger = logging.getLogger(__name__)


class CheckpointService:
    """
    Service for managing task checkpoints.

    Provides CRUD operations for checkpoints with support for:
    - Creating checkpoints when tasks start
    - Updating progress as tasks execute
    - Marking checkpoints as interrupted on failure
    - Resuming from interrupted checkpoints
    - Auto-cleanup of expired checkpoints
    """

    def __init__(self, db: Session):
        self.db = db

    def create_checkpoint(
        self,
        user_id: int,
        session_id: str,
        message_id: str,
        user_message: str,
        workspace_path: Optional[str] = None,
        total_steps: int = 0,
        expires_hours: int = 24,
    ) -> TaskCheckpoint:
        """
        Create a new checkpoint for a task.

        If a checkpoint already exists for this user/session, update it instead.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            message_id: Message ID for this task
            user_message: The original user request
            workspace_path: Optional workspace path
            total_steps: Total steps in the execution plan
            expires_hours: Hours until checkpoint expires (default 24)

        Returns:
            Created or updated TaskCheckpoint
        """
        # Check for existing checkpoint
        existing = self.get_checkpoint(user_id, session_id)

        if existing:
            # Update existing checkpoint with new task
            existing.message_id = message_id
            existing.user_message = user_message
            existing.workspace_path = workspace_path
            existing.status = "running"
            existing.current_step_index = 0
            existing.total_steps = total_steps
            existing.steps = []
            existing.modified_files = []
            existing.executed_commands = []
            existing.partial_content = None
            existing.streaming_state = {}
            existing.interrupted_at = None
            existing.interrupt_reason = None
            existing.retry_count = 0
            existing.last_retry_at = None
            existing.expires_at = datetime.now(timezone.utc) + timedelta(
                hours=expires_hours
            )
            existing.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(existing)
            logger.info(
                "Updated existing checkpoint",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "message_id": message_id,
                },
            )
            return existing

        # Create new checkpoint
        checkpoint = TaskCheckpoint(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            user_message=user_message,
            workspace_path=workspace_path,
            status="running",
            total_steps=total_steps,
            steps=[],
            modified_files=[],
            executed_commands=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        )

        self.db.add(checkpoint)
        self.db.commit()
        self.db.refresh(checkpoint)

        logger.info(
            "Created new checkpoint",
            extra={
                "checkpoint_id": str(checkpoint.id),
                "user_id": user_id,
                "session_id": session_id,
            },
        )
        return checkpoint

    def get_checkpoint(
        self,
        user_id: int,
        session_id: str,
    ) -> Optional[TaskCheckpoint]:
        """
        Get the checkpoint for a user/session.

        Args:
            user_id: The user ID
            session_id: Frontend session ID

        Returns:
            TaskCheckpoint if found, None otherwise
        """
        result = self.db.execute(
            select(TaskCheckpoint).where(
                and_(
                    TaskCheckpoint.user_id == user_id,
                    TaskCheckpoint.session_id == session_id,
                )
            )
        )
        return result.scalar_one_or_none()

    def get_checkpoint_by_id(
        self,
        checkpoint_id: str,
        user_id: int,
    ) -> Optional[TaskCheckpoint]:
        """
        Get a checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID
            user_id: The user ID (for authorization)

        Returns:
            TaskCheckpoint if found and authorized, None otherwise
        """
        try:
            uuid_id = UUID(checkpoint_id)
        except ValueError:
            return None

        result = self.db.execute(
            select(TaskCheckpoint).where(
                and_(
                    TaskCheckpoint.id == uuid_id,
                    TaskCheckpoint.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    def update_progress(
        self,
        user_id: int,
        session_id: str,
        current_step_index: Optional[int] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        partial_content: Optional[str] = None,
        streaming_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskCheckpoint]:
        """
        Update checkpoint progress.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            current_step_index: Current step being executed
            steps: Updated steps list with status
            partial_content: Accumulated partial content
            streaming_state: Current streaming state

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        if current_step_index is not None:
            checkpoint.current_step_index = current_step_index
        if steps is not None:
            checkpoint.steps = steps
            checkpoint.total_steps = len(steps)
        if partial_content is not None:
            checkpoint.partial_content = partial_content
        if streaming_state is not None:
            checkpoint.streaming_state = streaming_state

        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def add_modified_file(
        self,
        user_id: int,
        session_id: str,
        file_path: str,
        operation: str,
        success: bool = True,
    ) -> Optional[TaskCheckpoint]:
        """
        Add a modified file to the checkpoint.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            file_path: Path to the modified file
            operation: Type of operation (create, edit, delete)
            success: Whether the operation succeeded

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        modified_files = checkpoint.modified_files or []
        modified_files.append(
            {
                "path": file_path,
                "operation": operation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": success,
            }
        )
        checkpoint.modified_files = modified_files
        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def add_executed_command(
        self,
        user_id: int,
        session_id: str,
        command: str,
        exit_code: Optional[int] = None,
        success: bool = True,
    ) -> Optional[TaskCheckpoint]:
        """
        Add an executed command to the checkpoint.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            command: The command that was executed
            exit_code: Command exit code
            success: Whether the command succeeded

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        executed_commands = checkpoint.executed_commands or []
        executed_commands.append(
            {
                "command": command,
                "exitCode": exit_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": success,
            }
        )
        checkpoint.executed_commands = executed_commands
        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def mark_interrupted(
        self,
        user_id: int,
        session_id: str,
        reason: str = "Connection lost",
    ) -> Optional[TaskCheckpoint]:
        """
        Mark a checkpoint as interrupted.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            reason: Reason for interruption

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        checkpoint.status = "interrupted"
        checkpoint.interrupted_at = datetime.now(timezone.utc)
        checkpoint.interrupt_reason = reason
        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)

        logger.info(
            "Marked checkpoint as interrupted",
            extra={"checkpoint_id": str(checkpoint.id), "reason": reason},
        )
        return checkpoint

    def mark_completed(
        self,
        user_id: int,
        session_id: str,
    ) -> Optional[TaskCheckpoint]:
        """
        Mark a checkpoint as completed.

        Args:
            user_id: The user ID
            session_id: Frontend session ID

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        checkpoint.status = "completed"
        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)

        logger.info(
            "Marked checkpoint as completed",
            extra={"checkpoint_id": str(checkpoint.id)},
        )
        return checkpoint

    def mark_failed(
        self,
        user_id: int,
        session_id: str,
        reason: str = "Task failed",
    ) -> Optional[TaskCheckpoint]:
        """
        Mark a checkpoint as failed.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            reason: Reason for failure

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        checkpoint.status = "failed"
        checkpoint.interrupt_reason = reason
        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)

        logger.info(
            "Marked checkpoint as failed",
            extra={"checkpoint_id": str(checkpoint.id), "reason": reason},
        )
        return checkpoint

    def increment_retry(
        self,
        user_id: int,
        session_id: str,
    ) -> Optional[TaskCheckpoint]:
        """
        Increment the retry count for a checkpoint.

        Args:
            user_id: The user ID
            session_id: Frontend session ID

        Returns:
            Updated TaskCheckpoint or None if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return None

        checkpoint.retry_count += 1
        checkpoint.last_retry_at = datetime.now(timezone.utc)
        checkpoint.status = "running"  # Reset to running on retry
        checkpoint.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint

    def get_interrupted_checkpoints(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[TaskCheckpoint]:
        """
        Get interrupted checkpoints for a user.

        Args:
            user_id: The user ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of interrupted TaskCheckpoints
        """
        result = self.db.execute(
            select(TaskCheckpoint)
            .where(
                and_(
                    TaskCheckpoint.user_id == user_id,
                    TaskCheckpoint.status == "interrupted",
                    or_(
                        TaskCheckpoint.expires_at.is_(None),
                        TaskCheckpoint.expires_at > datetime.now(timezone.utc),
                    ),
                )
            )
            .order_by(TaskCheckpoint.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def delete_checkpoint(
        self,
        user_id: int,
        session_id: str,
    ) -> bool:
        """
        Delete a checkpoint.

        Args:
            user_id: The user ID
            session_id: Frontend session ID

        Returns:
            True if deleted, False if not found
        """
        checkpoint = self.get_checkpoint(user_id, session_id)
        if not checkpoint:
            return False

        self.db.delete(checkpoint)
        self.db.commit()

        logger.info(
            "Deleted checkpoint", extra={"user_id": user_id, "session_id": session_id}
        )
        return True

    def cleanup_expired(self) -> int:
        """
        Delete expired checkpoints.

        Returns:
            Number of checkpoints deleted
        """
        result = self.db.execute(
            delete(TaskCheckpoint).where(
                and_(
                    TaskCheckpoint.expires_at.isnot(None),
                    TaskCheckpoint.expires_at < datetime.now(timezone.utc),
                )
            )
        )
        self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired checkpoints")
        return count

    def sync_from_frontend(
        self,
        user_id: int,
        session_id: str,
        checkpoint_data: Dict[str, Any],
    ) -> TaskCheckpoint:
        """
        Sync checkpoint data from frontend localStorage.

        This allows the frontend to push its checkpoint state to the backend
        for cross-device persistence.

        Args:
            user_id: The user ID
            session_id: Frontend session ID
            checkpoint_data: Checkpoint data from frontend

        Returns:
            Synced TaskCheckpoint
        """
        existing = self.get_checkpoint(user_id, session_id)

        if existing:
            # Update existing checkpoint with frontend data
            existing.message_id = checkpoint_data.get("messageId", existing.message_id)
            existing.user_message = checkpoint_data.get(
                "userMessage", existing.user_message
            )
            existing.workspace_path = checkpoint_data.get(
                "workspacePath", existing.workspace_path
            )
            existing.status = checkpoint_data.get("status", existing.status)
            existing.current_step_index = checkpoint_data.get(
                "currentStepIndex", existing.current_step_index
            )
            existing.total_steps = checkpoint_data.get(
                "totalSteps", existing.total_steps
            )
            existing.steps = checkpoint_data.get("steps", existing.steps)
            existing.modified_files = checkpoint_data.get(
                "modifiedFiles", existing.modified_files
            )
            existing.executed_commands = checkpoint_data.get(
                "executedCommands", existing.executed_commands
            )
            existing.partial_content = checkpoint_data.get(
                "partialContent", existing.partial_content
            )
            existing.streaming_state = checkpoint_data.get(
                "streamingState", existing.streaming_state
            )
            existing.retry_count = checkpoint_data.get(
                "retryCount", existing.retry_count
            )
            existing.updated_at = datetime.now(timezone.utc)

            if checkpoint_data.get("interruptedAt"):
                existing.interrupted_at = datetime.fromisoformat(
                    checkpoint_data["interruptedAt"].replace("Z", "+00:00")
                )

            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Create new checkpoint from frontend data
        checkpoint = TaskCheckpoint(
            user_id=user_id,
            session_id=session_id,
            message_id=checkpoint_data.get("messageId", ""),
            user_message=checkpoint_data.get("userMessage", ""),
            workspace_path=checkpoint_data.get("workspacePath"),
            status=checkpoint_data.get("status", "running"),
            current_step_index=checkpoint_data.get("currentStepIndex", 0),
            total_steps=checkpoint_data.get("totalSteps", 0),
            steps=checkpoint_data.get("steps", []),
            modified_files=checkpoint_data.get("modifiedFiles", []),
            executed_commands=checkpoint_data.get("executedCommands", []),
            partial_content=checkpoint_data.get("partialContent"),
            streaming_state=checkpoint_data.get("streamingState", {}),
            retry_count=checkpoint_data.get("retryCount", 0),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        if checkpoint_data.get("interruptedAt"):
            checkpoint.interrupted_at = datetime.fromisoformat(
                checkpoint_data["interruptedAt"].replace("Z", "+00:00")
            )

        self.db.add(checkpoint)
        self.db.commit()
        self.db.refresh(checkpoint)
        return checkpoint
