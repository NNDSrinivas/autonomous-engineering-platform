"""
Checkpoint Persistence Service

Provides crash-recovery for enterprise projects by persisting and restoring
complete execution state to/from the database.

Key capabilities:
- Save checkpoints at configurable intervals
- Restore from any valid checkpoint
- Summarize context when conversation history grows large
- Handle checkpoint expiration and cleanup
- Support for all LLM providers with BYOK

Example:
    service = CheckpointPersistenceService(db_session, project_id)

    # Save checkpoint
    checkpoint_id = await service.save_checkpoint(
        task_context=context,
        checkpoint_type="automatic",
        reason="Iteration 10 checkpoint"
    )

    # Restore from checkpoint
    context = await service.restore_from_checkpoint(checkpoint_id)

    # Get latest valid checkpoint
    checkpoint = await service.get_latest_checkpoint()
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict

from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.models.enterprise_checkpoint import EnterpriseCheckpoint
from backend.database.models.enterprise_project import (
    EnterpriseProject,
    ProjectTaskQueue,
)

logger = logging.getLogger(__name__)


# Maximum conversation history entries before summarization
MAX_HISTORY_ENTRIES = 100
# Maximum tokens in history before forced summarization
MAX_HISTORY_TOKENS_ESTIMATE = 50000
# Default checkpoint expiration (30 days)
DEFAULT_CHECKPOINT_EXPIRY_DAYS = 30


class CheckpointPersistenceService:
    """
    Handles checkpoint persistence for enterprise project crash recovery.

    Supports all LLM providers for context summarization with BYOK.
    """

    def __init__(
        self,
        db_session: Session,
        project_id: str,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
    ):
        """
        Initialize checkpoint persistence service.

        Args:
            db_session: Database session
            project_id: Enterprise project ID
            llm_provider: LLM provider for summarization (openai, anthropic, etc.)
            llm_model: Model to use for summarization
            llm_api_key: Optional BYOK API key
        """
        self.db = db_session
        self.project_id = project_id
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key

    async def save_checkpoint(
        self,
        task_context: Any,  # TaskContext from autonomous_agent
        checkpoint_type: str = "automatic",
        reason: Optional[str] = None,
        current_task_id: Optional[str] = None,
        summarize_if_large: bool = True,
    ) -> str:
        """
        Save a checkpoint to the database.

        Args:
            task_context: The TaskContext from autonomous agent
            checkpoint_type: Type of checkpoint (automatic, manual, pre_gate, etc.)
            reason: Reason for creating checkpoint
            current_task_id: ID of task being executed
            summarize_if_large: Whether to summarize large histories

        Returns:
            Checkpoint ID
        """
        logger.info(
            f"Saving checkpoint for project {self.project_id} "
            f"at iteration {task_context.iteration}"
        )

        # Extract state from TaskContext
        agent_state = self._extract_agent_state(task_context)
        conversation_history = list(task_context.conversation_history)

        # Check if we need to summarize
        is_summarized = False
        context_summary = None

        if summarize_if_large and self._should_summarize(conversation_history):
            logger.info("Conversation history is large, summarizing...")
            context_summary = await self._summarize_context(
                conversation_history,
                task_context.original_request,
            )
            is_summarized = True
            # Keep only recent history plus summary
            conversation_history = conversation_history[-20:]  # Keep last 20 entries

        # Get task queue state
        completed_tasks, pending_tasks = self._get_task_queue_state()

        # Extract file snapshots for critical files
        file_snapshots = self._get_file_snapshots(
            task_context.workspace_path,
            task_context.files_modified[:10],  # Snapshot last 10 modified files
        )

        # Create checkpoint
        checkpoint = EnterpriseCheckpoint(
            project_id=self.project_id,
            task_id=current_task_id,
            checkpoint_type=checkpoint_type,
            iteration_number=task_context.iteration,
            checkpoint_reason=reason
            or f"Checkpoint at iteration {task_context.iteration}",
            agent_state=agent_state,
            conversation_history=conversation_history,
            tool_call_history=self._extract_tool_calls(task_context),
            files_modified=task_context.files_modified,
            files_created=task_context.files_created,
            file_snapshots=file_snapshots,
            error_history=[
                asdict(e) if hasattr(e, "__dict__") else e
                for e in task_context.error_history
            ],
            failed_approaches=[
                asdict(f) if hasattr(f, "__dict__") else f
                for f in task_context.failed_approaches
            ],
            completed_tasks=completed_tasks,
            pending_tasks=pending_tasks,
            current_task_progress=self._get_current_task_progress(current_task_id),
            context_summary=context_summary,
            is_context_summarized=is_summarized,
            verification_results=[
                asdict(v) if hasattr(v, "__dict__") else v
                for v in task_context.verification_results
            ],
            is_valid=True,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=DEFAULT_CHECKPOINT_EXPIRY_DAYS),
        )

        self.db.add(checkpoint)
        self.db.commit()
        self.db.refresh(checkpoint)

        # Update project's last checkpoint iteration
        project = (
            self.db.query(EnterpriseProject)
            .filter(EnterpriseProject.id == self.project_id)
            .first()
        )
        if project:
            project.last_checkpoint_iteration = task_context.iteration
            self.db.commit()

        logger.info(f"Checkpoint {checkpoint.id} saved successfully")
        return str(checkpoint.id)

    async def restore_from_checkpoint(
        self,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Restore execution state from a checkpoint.

        Args:
            checkpoint_id: Specific checkpoint to restore (latest if None)

        Returns:
            Restored state dict that can be used to recreate TaskContext
        """
        if checkpoint_id:
            checkpoint = (
                self.db.query(EnterpriseCheckpoint)
                .filter(
                    EnterpriseCheckpoint.id == checkpoint_id,
                    EnterpriseCheckpoint.is_valid,
                )
                .first()
            )
        else:
            checkpoint = self.get_latest_checkpoint()

        if not checkpoint:
            logger.warning(f"No valid checkpoint found for project {self.project_id}")
            return None

        logger.info(
            f"Restoring from checkpoint {checkpoint.id} "
            f"at iteration {checkpoint.iteration_number}"
        )

        # Update restored count
        checkpoint.restored_count += 1
        self.db.commit()

        # Build restoration state
        restored_state = {
            "checkpoint_id": str(checkpoint.id),
            "iteration": checkpoint.iteration_number,
            "agent_state": checkpoint.agent_state,
            "conversation_history": checkpoint.conversation_history,
            "context_summary": checkpoint.context_summary,
            "is_context_summarized": checkpoint.is_context_summarized,
            "files_modified": checkpoint.files_modified,
            "files_created": checkpoint.files_created,
            "file_snapshots": checkpoint.file_snapshots,
            "error_history": checkpoint.error_history,
            "failed_approaches": checkpoint.failed_approaches,
            "completed_tasks": checkpoint.completed_tasks,
            "pending_tasks": checkpoint.pending_tasks,
            "current_task_progress": checkpoint.current_task_progress,
            "verification_results": checkpoint.verification_results,
            "tool_call_history": checkpoint.tool_call_history,
        }

        logger.info(f"Restored state from checkpoint {checkpoint.id}")
        return restored_state

    def get_latest_checkpoint(self) -> Optional[EnterpriseCheckpoint]:
        """Get the most recent valid checkpoint for this project."""
        return (
            self.db.query(EnterpriseCheckpoint)
            .filter(
                EnterpriseCheckpoint.project_id == self.project_id,
                EnterpriseCheckpoint.is_valid,
            )
            .order_by(desc(EnterpriseCheckpoint.iteration_number))
            .first()
        )

    def get_checkpoint_by_iteration(
        self,
        iteration: int,
    ) -> Optional[EnterpriseCheckpoint]:
        """Get checkpoint closest to a specific iteration."""
        return (
            self.db.query(EnterpriseCheckpoint)
            .filter(
                EnterpriseCheckpoint.project_id == self.project_id,
                EnterpriseCheckpoint.iteration_number <= iteration,
                EnterpriseCheckpoint.is_valid,
            )
            .order_by(desc(EnterpriseCheckpoint.iteration_number))
            .first()
        )

    def list_checkpoints(
        self,
        limit: int = 10,
        include_invalid: bool = False,
    ) -> List[EnterpriseCheckpoint]:
        """List checkpoints for this project."""
        query = self.db.query(EnterpriseCheckpoint).filter(
            EnterpriseCheckpoint.project_id == self.project_id,
        )

        if not include_invalid:
            query = query.filter(EnterpriseCheckpoint.is_valid)

        return query.order_by(desc(EnterpriseCheckpoint.created_at)).limit(limit).all()

    def invalidate_checkpoint(
        self,
        checkpoint_id: str,
        reason: str,
    ) -> bool:
        """Mark a checkpoint as invalid."""
        checkpoint = (
            self.db.query(EnterpriseCheckpoint)
            .filter(
                EnterpriseCheckpoint.id == checkpoint_id,
            )
            .first()
        )

        if checkpoint:
            checkpoint.is_valid = False
            checkpoint.invalidation_reason = reason
            self.db.commit()
            logger.info(f"Invalidated checkpoint {checkpoint_id}: {reason}")
            return True
        return False

    def cleanup_expired_checkpoints(self) -> int:
        """Delete expired checkpoints. Returns count of deleted checkpoints."""
        now = datetime.now(timezone.utc)
        expired = (
            self.db.query(EnterpriseCheckpoint)
            .filter(
                EnterpriseCheckpoint.project_id == self.project_id,
                EnterpriseCheckpoint.expires_at < now,
            )
            .all()
        )

        count = len(expired)
        for checkpoint in expired:
            self.db.delete(checkpoint)

        self.db.commit()
        logger.info(f"Cleaned up {count} expired checkpoints")
        return count

    def _extract_agent_state(self, task_context: Any) -> Dict[str, Any]:
        """Extract serializable agent state from TaskContext."""
        return {
            "task_id": task_context.task_id,
            "original_request": task_context.original_request,
            "workspace_path": task_context.workspace_path,
            "status": (
                task_context.status.value
                if hasattr(task_context.status, "value")
                else str(task_context.status)
            ),
            "complexity": (
                task_context.complexity.value
                if hasattr(task_context.complexity, "value")
                else str(task_context.complexity)
            ),
            "project_type": task_context.project_type,
            "framework": task_context.framework,
            "plan_id": task_context.plan_id,
            "current_step_index": task_context.current_step_index,
            "step_count": task_context.step_count,
            "enterprise_project_id": task_context.enterprise_project_id,
            "checkpoint_interval": task_context.checkpoint_interval,
            "consecutive_same_error_count": task_context.consecutive_same_error_count,
        }

    def _extract_tool_calls(self, task_context: Any) -> List[Dict[str, Any]]:
        """Extract tool call history from TaskContext."""
        tool_calls = []
        for iteration, calls in task_context.tool_calls_per_iteration.items():
            for call in calls:
                tool_calls.append(
                    {
                        "iteration": iteration,
                        "tool": call,
                    }
                )
        return tool_calls[-100:]  # Keep last 100 tool calls

    def _should_summarize(self, conversation_history: List[Dict]) -> bool:
        """Check if conversation history should be summarized."""
        if len(conversation_history) > MAX_HISTORY_ENTRIES:
            return True

        # Rough token estimate
        total_chars = sum(
            len(str(entry.get("content", ""))) for entry in conversation_history
        )
        estimated_tokens = total_chars / 4  # Rough estimate

        return estimated_tokens > MAX_HISTORY_TOKENS_ESTIMATE

    async def _summarize_context(
        self,
        conversation_history: List[Dict],
        original_request: str,
    ) -> str:
        """Use LLM to summarize conversation context."""
        from backend.services.llm_client import LLMClient

        client = LLMClient(
            provider=self.llm_provider,
            model=self.llm_model,
            api_key=self.llm_api_key,
            temperature=0.3,
            max_tokens=2000,
        )

        # Build summary prompt
        history_text = "\n".join(
            [
                f"{entry.get('role', 'unknown')}: {entry.get('content', '')[:500]}"
                for entry in conversation_history[-50:]  # Last 50 entries
            ]
        )

        prompt = f"""Summarize this conversation history for a software development task.
Focus on:
1. What has been accomplished (files created/modified, features implemented)
2. Current state (what was being worked on)
3. Errors encountered and how they were resolved
4. Important decisions made
5. What still needs to be done

Original task: {original_request}

Conversation history (last 50 entries):
{history_text}

Provide a concise summary (500-1000 words) that captures all essential context needed to continue the work."""

        try:
            response = await client.complete(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Failed to summarize context: {e}")
            # Fallback to simple extraction
            return self._simple_summary(conversation_history, original_request)

    def _simple_summary(
        self,
        conversation_history: List[Dict],
        original_request: str,
    ) -> str:
        """Create a simple summary without LLM."""
        summary_parts = [f"Original task: {original_request}"]

        # Extract key actions
        for entry in conversation_history[-20:]:
            content = str(entry.get("content", ""))
            if any(
                keyword in content.lower()
                for keyword in [
                    "created",
                    "modified",
                    "error",
                    "success",
                    "completed",
                    "fixed",
                ]
            ):
                summary_parts.append(content[:200])

        return "\n\n".join(summary_parts[:10])

    def _get_task_queue_state(self) -> Tuple[List[str], List[str]]:
        """Get current state of task queue."""
        tasks = (
            self.db.query(ProjectTaskQueue)
            .filter(
                ProjectTaskQueue.project_id == self.project_id,
            )
            .all()
        )

        completed = [str(t.id) for t in tasks if t.status == "completed"]
        pending = [
            str(t.id) for t in tasks if t.status in ["pending", "ready", "in_progress"]
        ]

        return completed, pending

    def _get_current_task_progress(
        self,
        task_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Get progress on current task."""
        if not task_id:
            return None

        task = (
            self.db.query(ProjectTaskQueue)
            .filter(
                ProjectTaskQueue.id == task_id,
            )
            .first()
        )

        if task:
            return {
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status,
                "progress_percentage": task.progress_percentage,
                "started_at": task.started_at.isoformat() if task.started_at else None,
            }
        return None

    def _get_file_snapshots(
        self,
        workspace_path: str,
        files: List[str],
    ) -> Dict[str, str]:
        """Get content snapshots of files."""
        import os

        snapshots = {}
        for file_path in files[:10]:  # Limit to 10 files
            full_path = (
                os.path.join(workspace_path, file_path)
                if not os.path.isabs(file_path)
                else file_path
            )
            try:
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if len(content) < 50000:  # Only snapshot files under 50KB
                            snapshots[file_path] = content
            except Exception as e:
                logger.debug(f"Could not snapshot {file_path}: {e}")

        return snapshots


async def create_checkpoint(
    db_session: Session,
    project_id: str,
    task_context: Any,
    checkpoint_type: str = "automatic",
    reason: Optional[str] = None,
    llm_provider: str = "openai",
    llm_api_key: Optional[str] = None,
) -> str:
    """
    Convenience function to create a checkpoint.

    Args:
        db_session: Database session
        project_id: Enterprise project ID
        task_context: TaskContext from autonomous agent
        checkpoint_type: Type of checkpoint
        reason: Reason for checkpoint
        llm_provider: LLM provider for summarization
        llm_api_key: Optional BYOK API key

    Returns:
        Checkpoint ID
    """
    service = CheckpointPersistenceService(
        db_session=db_session,
        project_id=project_id,
        llm_provider=llm_provider,
        llm_api_key=llm_api_key,
    )
    return await service.save_checkpoint(
        task_context=task_context,
        checkpoint_type=checkpoint_type,
        reason=reason,
    )


async def restore_checkpoint(
    db_session: Session,
    project_id: str,
    checkpoint_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to restore from checkpoint.

    Args:
        db_session: Database session
        project_id: Enterprise project ID
        checkpoint_id: Specific checkpoint (latest if None)

    Returns:
        Restored state dict
    """
    service = CheckpointPersistenceService(
        db_session=db_session,
        project_id=project_id,
    )
    return await service.restore_from_checkpoint(checkpoint_id)
