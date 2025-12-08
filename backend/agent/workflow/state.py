"""
Workflow State Machine

Tracks the state of autonomous task execution across multiple steps.
This is the "brain state" that remembers where NAVI is in a multi-step workflow.
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""

    PENDING = "pending"  # Not started
    IN_PROGRESS = "in_progress"  # Currently executing
    WAITING_APPROVAL = "waiting_approval"  # Waiting for user approval
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Failed with error
    CANCELLED = "cancelled"  # User cancelled


class WorkflowState:
    """
    State machine for autonomous workflow execution.

    Tracks progress through the 10-step autonomous engineering workflow:
    1. analysis → understand task and generate plan
    2. locate_files → find relevant code files
    3. propose_diffs → generate code changes
    4. apply_diffs → apply approved changes
    5. run_tests → execute test suite
    6. commit_changes → git commit
    7. push_branch → git push
    8. create_pr → create pull request
    9. update_jira → update Jira status
    10. done → workflow complete
    """

    # Define workflow step order
    STEP_ORDER = [
        "analysis",
        "locate_files",
        "propose_diffs",
        "apply_diffs",
        "run_tests",
        "commit_changes",
        "push_branch",
        "create_pr",
        "update_jira",
        "done",
    ]

    def __init__(self, issue_id: str, user_id: str):
        """
        Initialize workflow state.

        Args:
            issue_id: Jira issue key (e.g., "SCRUM-123")
            user_id: User executing the workflow
        """
        self.issue_id = issue_id
        self.user_id = user_id
        self.status = WorkflowStatus.PENDING
        self.current_step = "analysis"
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None

        # Step-specific data
        self.issue: Optional[Dict[str, Any]] = None
        self.enriched_context: Optional[Dict[str, Any]] = None
        self.plan: Optional[Dict[str, Any]] = None
        self.file_targets: List[str] = []
        self.diff_proposals: List[Dict[str, Any]] = []
        self.test_results: Optional[Dict[str, Any]] = None
        self.branch_name: Optional[str] = None
        self.commit_sha: Optional[str] = None
        self.pr_number: Optional[int] = None
        self.pr_url: Optional[str] = None

        # Execution history
        self.step_history: List[Dict[str, Any]] = []
        self.errors: List[Union[str, Dict[str, Any]]] = (
            []
        )  # Can store string or dict errors

        # Approval tracking
        self.pending_approval: Optional[Dict[str, Any]] = None

        logger.info(f"Created workflow state for {issue_id} by {user_id}")

    def next_step(self) -> str:
        """
        Advance to the next step in the workflow.

        Returns:
            Next step name
        """
        try:
            current_idx = self.STEP_ORDER.index(self.current_step)
            if current_idx < len(self.STEP_ORDER) - 1:
                self.current_step = self.STEP_ORDER[current_idx + 1]
                self.updated_at = datetime.utcnow()
                logger.info(
                    f"Workflow {self.issue_id} advanced to step: {self.current_step}"
                )
            else:
                logger.info(f"Workflow {self.issue_id} already at final step")

            return self.current_step
        except ValueError:
            logger.error(f"Current step {self.current_step} not in STEP_ORDER")
            return self.current_step

    def record_step_completion(self, step: str, result: Dict[str, Any]):
        """
        Record completion of a workflow step.

        Args:
            step: Step name
            result: Step execution result
        """
        self.step_history.append(
            {"step": step, "timestamp": datetime.utcnow().isoformat(), "result": result}
        )
        self.updated_at = datetime.utcnow()
        logger.info(f"Recorded completion of step {step} for workflow {self.issue_id}")

    def record_error(self, error: str):
        """
        Record an error during workflow execution.

        Args:
            error: Error message
        """
        self.errors.append(
            {
                "step": self.current_step,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self.updated_at = datetime.utcnow()
        logger.error(f"Recorded error in workflow {self.issue_id}: {error}")

    def set_waiting_approval(self, approval_data: Dict[str, Any]):
        """
        Mark workflow as waiting for user approval.

        Args:
            approval_data: Data about what needs approval
        """
        self.status = WorkflowStatus.WAITING_APPROVAL
        self.pending_approval = approval_data
        self.updated_at = datetime.utcnow()
        logger.info(
            f"Workflow {self.issue_id} waiting for approval at step {self.current_step}"
        )

    def approve(self):
        """User approved pending action."""
        self.status = WorkflowStatus.IN_PROGRESS
        self.pending_approval = None
        self.updated_at = datetime.utcnow()
        logger.info(f"Workflow {self.issue_id} approved by user")

    def reject(self, reason: Optional[str] = None):
        """User rejected pending action."""
        self.status = WorkflowStatus.CANCELLED
        if reason:
            self.record_error(f"User rejected: {reason}")
        self.updated_at = datetime.utcnow()
        logger.info(f"Workflow {self.issue_id} rejected by user")

    def complete(self):
        """Mark workflow as completed."""
        self.status = WorkflowStatus.COMPLETED
        self.current_step = "done"
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        logger.info(f"Workflow {self.issue_id} completed successfully")

    def fail(self, error: str):
        """Mark workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.record_error(error)
        self.updated_at = datetime.utcnow()
        logger.error(f"Workflow {self.issue_id} failed: {error}")

    def cancel(self):
        """Cancel workflow."""
        self.status = WorkflowStatus.CANCELLED
        self.updated_at = datetime.utcnow()
        logger.info(f"Workflow {self.issue_id} cancelled")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary for serialization.

        Returns:
            Dict representation of workflow state
        """
        return {
            "issue_id": self.issue_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "current_step": self.current_step,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "issue": self.issue,
            "plan": self.plan,
            "file_targets": self.file_targets,
            "diff_proposals": self.diff_proposals,
            "test_results": self.test_results,
            "branch_name": self.branch_name,
            "commit_sha": self.commit_sha,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "step_history": self.step_history,
            "errors": self.errors,
            "pending_approval": self.pending_approval,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """
        Reconstruct WorkflowState from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            WorkflowState instance
        """
        state = cls(data["issue_id"], data["user_id"])
        state.status = WorkflowStatus(data["status"])
        state.current_step = data["current_step"]
        state.started_at = datetime.fromisoformat(data["started_at"])
        state.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("completed_at"):
            state.completed_at = datetime.fromisoformat(data["completed_at"])

        state.issue = data.get("issue")
        state.plan = data.get("plan")
        state.file_targets = data.get("file_targets", [])
        state.diff_proposals = data.get("diff_proposals", [])
        state.test_results = data.get("test_results")
        state.branch_name = data.get("branch_name")
        state.commit_sha = data.get("commit_sha")
        state.pr_number = data.get("pr_number")
        state.pr_url = data.get("pr_url")
        state.step_history = data.get("step_history", [])
        state.errors = data.get("errors", [])
        state.pending_approval = data.get("pending_approval")

        return state

    def get_progress_percentage(self) -> int:
        """
        Calculate workflow progress percentage.

        Returns:
            Progress percentage (0-100)
        """
        try:
            current_idx = self.STEP_ORDER.index(self.current_step)
            return int((current_idx / len(self.STEP_ORDER)) * 100)
        except ValueError:
            return 0

    def get_progress_summary(self) -> str:
        """
        Get human-readable progress summary.

        Returns:
            Progress summary string
        """
        percentage = self.get_progress_percentage()
        return f"{self.current_step} ({percentage}%) - {self.status.value}"
