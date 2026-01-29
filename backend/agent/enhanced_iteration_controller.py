"""
Enhanced Iteration Controller - Enterprise-grade iteration management for NAVI.

Extends the base IterationController with capabilities needed for enterprise
projects that span weeks/months of development:

1. UNLIMITED ITERATIONS - No hardcoded limits for enterprise mode
2. SMART CHECKPOINTING - Automatic state saves every N iterations
3. CONTEXT OVERFLOW DETECTION - Detects when context is getting too large
4. CHECKPOINT RESUME - Seamless resume from any checkpoint
5. ENTERPRISE PROJECT INTEGRATION - Links with EnterpriseProject state

This enables building full enterprise applications like e-commerce platforms,
microservices architectures, and large-scale systems.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Awaitable
from enum import Enum
from datetime import datetime
import logging
import hashlib

from backend.agent.iteration_controller import (
    IterationConfig,
    IterationMode,
    IterationResult,
)

logger = logging.getLogger(__name__)


class EnterpriseIterationMode(Enum):
    """Extended iteration modes for enterprise projects."""

    # Standard modes (inherited semantics)
    ONE_SHOT = "one_shot"
    UNTIL_TESTS_PASS = "until_tests_pass"
    UNTIL_NO_ERRORS = "until_no_errors"
    MAX_ITERATIONS = "max_iterations"

    # Enterprise modes
    ENTERPRISE = "enterprise"  # Unlimited with checkpointing
    UNTIL_MILESTONE = "until_milestone"  # Run until milestone complete
    UNTIL_GATE = "until_gate"  # Run until human checkpoint gate


@dataclass
class EnterpriseIterationConfig:
    """Configuration for enterprise iterative execution."""

    mode: EnterpriseIterationMode = EnterpriseIterationMode.ONE_SHOT

    # Iteration limits - None means unlimited
    max_iterations: Optional[int] = None

    # Checkpointing settings
    checkpoint_interval: int = 10  # Create checkpoint every N iterations
    checkpoint_on_milestone: bool = True  # Checkpoint when milestone reached
    checkpoint_on_error: bool = True  # Checkpoint on errors for recovery

    # Context management
    max_context_tokens: int = 100000  # Estimated max context before overflow
    context_summarization_threshold: float = 0.8  # Summarize at 80% capacity

    # Stopping conditions
    stop_on_same_error: bool = True
    stop_on_no_progress: bool = True
    stop_on_human_gate: bool = True  # Pause for human checkpoints
    max_consecutive_failures: int = 5  # Stop after N failures in a row

    # Timeouts
    timeout_per_iteration_ms: int = 120000  # 2 minutes per iteration for complex tasks
    total_timeout_hours: Optional[float] = None  # No total timeout for enterprise

    # Enterprise project link
    enterprise_project_id: Optional[str] = None

    @classmethod
    def for_complexity(cls, complexity: str) -> "EnterpriseIterationConfig":
        """Create config based on task complexity."""
        configs = {
            "simple": cls(
                mode=EnterpriseIterationMode.MAX_ITERATIONS,
                max_iterations=8,
                checkpoint_interval=5,
            ),
            "medium": cls(
                mode=EnterpriseIterationMode.MAX_ITERATIONS,
                max_iterations=15,
                checkpoint_interval=8,
            ),
            "complex": cls(
                mode=EnterpriseIterationMode.MAX_ITERATIONS,
                max_iterations=25,
                checkpoint_interval=10,
            ),
            "enterprise": cls(
                mode=EnterpriseIterationMode.ENTERPRISE,
                max_iterations=None,  # Unlimited
                checkpoint_interval=10,
                max_consecutive_failures=10,
            ),
        }
        return configs.get(complexity, configs["medium"])

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "EnterpriseIterationConfig":
        """Create config from dictionary."""
        mode_str = config.get("mode", "one_shot")
        try:
            mode = EnterpriseIterationMode(mode_str)
        except ValueError:
            mode = EnterpriseIterationMode.ONE_SHOT

        return cls(
            mode=mode,
            max_iterations=config.get("max_iterations"),
            checkpoint_interval=config.get("checkpoint_interval", 10),
            checkpoint_on_milestone=config.get("checkpoint_on_milestone", True),
            checkpoint_on_error=config.get("checkpoint_on_error", True),
            max_context_tokens=config.get("max_context_tokens", 100000),
            context_summarization_threshold=config.get(
                "context_summarization_threshold", 0.8
            ),
            stop_on_same_error=config.get("stop_on_same_error", True),
            stop_on_no_progress=config.get("stop_on_no_progress", True),
            stop_on_human_gate=config.get("stop_on_human_gate", True),
            max_consecutive_failures=config.get("max_consecutive_failures", 5),
            timeout_per_iteration_ms=config.get("timeout_per_iteration_ms", 120000),
            total_timeout_hours=config.get("total_timeout_hours"),
            enterprise_project_id=config.get("enterprise_project_id"),
        )


@dataclass
class CheckpointData:
    """Data captured at a checkpoint for resume capability."""

    checkpoint_id: str
    iteration_number: int
    timestamp: datetime

    # Iteration state
    iteration_state: Dict[str, Any]

    # Context summary (what's been accomplished)
    context_summary: str
    key_decisions: List[str]
    files_modified: List[str]
    commands_executed: List[str]

    # Progress info
    completed_tasks: List[str]
    pending_tasks: List[str]
    current_task: Optional[str]

    # Enterprise project state
    project_state: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "iteration_number": self.iteration_number,
            "timestamp": self.timestamp.isoformat(),
            "iteration_state": self.iteration_state,
            "context_summary": self.context_summary,
            "key_decisions": self.key_decisions,
            "files_modified": self.files_modified,
            "commands_executed": self.commands_executed,
            "completed_tasks": self.completed_tasks,
            "pending_tasks": self.pending_tasks,
            "current_task": self.current_task,
            "project_state": self.project_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        """Create from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            iteration_number=data["iteration_number"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            iteration_state=data["iteration_state"],
            context_summary=data["context_summary"],
            key_decisions=data.get("key_decisions", []),
            files_modified=data.get("files_modified", []),
            commands_executed=data.get("commands_executed", []),
            completed_tasks=data.get("completed_tasks", []),
            pending_tasks=data.get("pending_tasks", []),
            current_task=data.get("current_task"),
            project_state=data.get("project_state"),
        )


@dataclass
class EnterpriseIterationState:
    """Extended iteration state for enterprise projects."""

    # Base iteration tracking
    iteration_count: int = 0
    errors_seen: List[str] = field(default_factory=list)
    test_counts: List[Dict[str, int]] = field(default_factory=list)
    results: List[IterationResult] = field(default_factory=list)
    success: bool = False
    stopped_reason: Optional[str] = None

    # Enterprise tracking
    consecutive_failures: int = 0
    total_duration_ms: int = 0
    checkpoints: List[str] = field(default_factory=list)  # Checkpoint IDs
    last_checkpoint_iteration: int = 0

    # Context tracking
    estimated_context_tokens: int = 0
    context_summarizations: int = 0

    # Milestone/gate tracking
    milestones_completed: List[str] = field(default_factory=list)
    pending_gates: List[str] = field(default_factory=list)
    current_gate: Optional[str] = None

    # Files and commands for checkpoint context
    all_modified_files: List[str] = field(default_factory=list)
    all_executed_commands: List[str] = field(default_factory=list)

    def should_continue(self, config: EnterpriseIterationConfig) -> bool:
        """Determine if iteration should continue."""
        # Already succeeded
        if self.success:
            logger.info("[ENTERPRISE_ITERATION] Stopping: success achieved")
            return False

        # Human gate requires attention
        if config.stop_on_human_gate and self.current_gate:
            self.stopped_reason = "human_gate_pending"
            logger.info("[ENTERPRISE_ITERATION] Pausing: human checkpoint gate pending")
            return False

        # Max iterations reached (if set)
        if config.max_iterations is not None:
            if self.iteration_count >= config.max_iterations:
                self.stopped_reason = "max_iterations_reached"
                logger.info(
                    "[ENTERPRISE_ITERATION] Stopping: max iterations (%d) reached",
                    config.max_iterations,
                )
                return False

        # Too many consecutive failures
        if self.consecutive_failures >= config.max_consecutive_failures:
            self.stopped_reason = "max_consecutive_failures"
            logger.info(
                "[ENTERPRISE_ITERATION] Stopping: %d consecutive failures",
                self.consecutive_failures,
            )
            return False

        # Same error twice in a row
        if config.stop_on_same_error and len(self.errors_seen) >= 2:
            if self.errors_seen[-1] == self.errors_seen[-2]:
                self.stopped_reason = "same_error_repeated"
                logger.info("[ENTERPRISE_ITERATION] Stopping: same error repeated")
                return False

        # No progress in test counts
        if config.stop_on_no_progress and len(self.test_counts) >= 3:
            # Check last 3 iterations
            recent = self.test_counts[-3:]
            failed_counts = [tc.get("failed", 0) for tc in recent]
            if failed_counts == sorted(failed_counts):  # Not improving
                self.stopped_reason = "no_progress"
                logger.info(
                    "[ENTERPRISE_ITERATION] Stopping: no progress in 3 iterations"
                )
                return False

        return True

    def should_checkpoint(self, config: EnterpriseIterationConfig) -> bool:
        """Determine if we should create a checkpoint now."""
        iterations_since_checkpoint = (
            self.iteration_count - self.last_checkpoint_iteration
        )

        # Regular interval checkpoint
        if iterations_since_checkpoint >= config.checkpoint_interval:
            return True

        # Context getting large
        if (
            self.estimated_context_tokens
            > config.max_context_tokens * config.context_summarization_threshold
        ):
            return True

        return False

    def should_summarize_context(self, config: EnterpriseIterationConfig) -> bool:
        """Determine if context should be summarized to save space."""
        return (
            self.estimated_context_tokens
            > config.max_context_tokens * config.context_summarization_threshold
        )

    def record_result(self, result: IterationResult, duration_ms: int = 0):
        """Record the result of an iteration."""
        self.results.append(result)
        self.iteration_count += 1
        self.total_duration_ms += duration_ms

        if result.success:
            self.success = True
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

        if result.error_hash:
            self.errors_seen.append(result.error_hash)
        else:
            self.consecutive_failures = 0  # Reset on non-error

        if result.test_results:
            self.test_counts.append(
                {
                    "total": result.test_results.get("total", 0),
                    "passed": result.test_results.get("passed", 0),
                    "failed": result.test_results.get("failed", 0),
                }
            )

    def record_checkpoint(self, checkpoint_id: str):
        """Record that a checkpoint was created."""
        self.checkpoints.append(checkpoint_id)
        self.last_checkpoint_iteration = self.iteration_count

    def record_context_summarization(self, new_token_estimate: int):
        """Record that context was summarized."""
        self.context_summarizations += 1
        self.estimated_context_tokens = new_token_estimate

    def record_milestone(self, milestone_id: str):
        """Record completion of a milestone."""
        self.milestones_completed.append(milestone_id)

    def set_gate(self, gate_id: Optional[str]):
        """Set the current human checkpoint gate."""
        if gate_id and self.current_gate != gate_id:
            self.pending_gates.append(gate_id)
        self.current_gate = gate_id

    def clear_gate(self):
        """Clear the current gate after human decision."""
        self.current_gate = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "iteration_count": self.iteration_count,
            "success": self.success,
            "stopped_reason": self.stopped_reason,
            "consecutive_failures": self.consecutive_failures,
            "total_duration_ms": self.total_duration_ms,
            "checkpoints": self.checkpoints,
            "last_checkpoint_iteration": self.last_checkpoint_iteration,
            "estimated_context_tokens": self.estimated_context_tokens,
            "context_summarizations": self.context_summarizations,
            "milestones_completed": self.milestones_completed,
            "pending_gates": self.pending_gates,
            "current_gate": self.current_gate,
            "test_counts": self.test_counts,
            "errors_seen_count": len(self.errors_seen),
            "results_summary": [
                {
                    "iteration": r.iteration_number,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                }
                for r in self.results[-10:]  # Last 10 results
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnterpriseIterationState":
        """Restore state from dictionary."""
        state = cls()
        state.iteration_count = data.get("iteration_count", 0)
        state.success = data.get("success", False)
        state.stopped_reason = data.get("stopped_reason")
        state.consecutive_failures = data.get("consecutive_failures", 0)
        state.total_duration_ms = data.get("total_duration_ms", 0)
        state.checkpoints = data.get("checkpoints", [])
        state.last_checkpoint_iteration = data.get("last_checkpoint_iteration", 0)
        state.estimated_context_tokens = data.get("estimated_context_tokens", 0)
        state.context_summarizations = data.get("context_summarizations", 0)
        state.milestones_completed = data.get("milestones_completed", [])
        state.pending_gates = data.get("pending_gates", [])
        state.current_gate = data.get("current_gate")
        state.test_counts = data.get("test_counts", [])
        return state


# Type for checkpoint save callback
CheckpointSaveCallback = Callable[[CheckpointData], Awaitable[str]]
ContextSummarizeCallback = Callable[[str], Awaitable[str]]


class EnhancedIterationController:
    """
    Enterprise-grade iteration controller for long-running projects.

    Extends the base IterationController with:
    - Unlimited iterations for enterprise mode
    - Smart checkpointing at configurable intervals
    - Context overflow detection and summarization
    - Human checkpoint gate integration
    - Enterprise project state tracking

    Usage:
        # Create for enterprise project
        controller = EnhancedIterationController.for_enterprise(
            project_id="proj_123",
            checkpoint_callback=save_checkpoint,
            summarize_callback=summarize_context,
        )

        # Main iteration loop
        while controller.should_iterate():
            result = await execute_iteration()
            controller.record_iteration(result)

            if controller.should_checkpoint():
                await controller.create_checkpoint(context)

            if controller.should_summarize():
                await controller.summarize_context()
    """

    def __init__(
        self,
        config: Optional[EnterpriseIterationConfig] = None,
        checkpoint_callback: Optional[CheckpointSaveCallback] = None,
        summarize_callback: Optional[ContextSummarizeCallback] = None,
    ):
        self.config = config or EnterpriseIterationConfig()
        self.state = EnterpriseIterationState()
        self.checkpoint_callback = checkpoint_callback
        self.summarize_callback = summarize_callback

        # For backwards compatibility with base controller
        self._base_config = IterationConfig(
            mode=(
                IterationMode.MAX_ITERATIONS
                if self.config.max_iterations
                else IterationMode.ONE_SHOT
            ),
            max_iterations=self.config.max_iterations or 999999,
            stop_on_same_error=self.config.stop_on_same_error,
            stop_on_no_progress=self.config.stop_on_no_progress,
            timeout_per_iteration_ms=self.config.timeout_per_iteration_ms,
        )

    @classmethod
    def for_enterprise(
        cls,
        project_id: str,
        checkpoint_callback: Optional[CheckpointSaveCallback] = None,
        summarize_callback: Optional[ContextSummarizeCallback] = None,
        **kwargs,
    ) -> "EnhancedIterationController":
        """Create controller for enterprise project (unlimited iterations)."""
        config = EnterpriseIterationConfig.for_complexity("enterprise")
        config.enterprise_project_id = project_id

        # Apply any overrides
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return cls(
            config=config,
            checkpoint_callback=checkpoint_callback,
            summarize_callback=summarize_callback,
        )

    @classmethod
    def for_complexity(
        cls,
        complexity: str,
        checkpoint_callback: Optional[CheckpointSaveCallback] = None,
        summarize_callback: Optional[ContextSummarizeCallback] = None,
    ) -> "EnhancedIterationController":
        """Create controller based on task complexity."""
        config = EnterpriseIterationConfig.for_complexity(complexity)
        return cls(
            config=config,
            checkpoint_callback=checkpoint_callback,
            summarize_callback=summarize_callback,
        )

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint: CheckpointData,
        config: Optional[EnterpriseIterationConfig] = None,
        checkpoint_callback: Optional[CheckpointSaveCallback] = None,
        summarize_callback: Optional[ContextSummarizeCallback] = None,
    ) -> "EnhancedIterationController":
        """Resume controller from a checkpoint."""
        controller = cls(
            config=config,
            checkpoint_callback=checkpoint_callback,
            summarize_callback=summarize_callback,
        )

        # Restore state from checkpoint
        controller.state = EnterpriseIterationState.from_dict(
            checkpoint.iteration_state
        )

        logger.info(
            "[ENTERPRISE_ITERATION] Resumed from checkpoint %s at iteration %d",
            checkpoint.checkpoint_id,
            checkpoint.iteration_number,
        )

        return controller

    def should_iterate(self) -> bool:
        """Check if we should continue iterating."""
        if self.config.mode == EnterpriseIterationMode.ONE_SHOT:
            return self.state.iteration_count == 0

        return self.state.should_continue(self.config)

    def should_checkpoint(self) -> bool:
        """Check if we should create a checkpoint now."""
        return self.state.should_checkpoint(self.config)

    def should_summarize(self) -> bool:
        """Check if context should be summarized."""
        return self.state.should_summarize_context(self.config)

    def record_iteration(
        self,
        success: bool,
        test_results: Optional[Dict[str, Any]] = None,
        debug_analysis: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0,
        modified_files: Optional[List[str]] = None,
        executed_commands: Optional[List[str]] = None,
        estimated_tokens: Optional[int] = None,
    ):
        """Record the result of an iteration."""
        # Generate error hash for deduplication
        error_hash = None
        if test_results and not success:
            failed_tests = test_results.get("failed_tests", [])
            if failed_tests:
                error_str = "|".join(
                    [
                        f"{t.get('name', '')}:{t.get('error_message', '')[:100]}"
                        for t in failed_tests
                    ]
                )
                error_hash = hashlib.md5(error_str.encode()).hexdigest()[:8]

        result = IterationResult(
            iteration_number=self.state.iteration_count + 1,
            success=success,
            plan_executed=True,
            test_results=test_results,
            debug_analysis=debug_analysis,
            error_hash=error_hash,
            duration_ms=duration_ms,
        )

        self.state.record_result(result, duration_ms)

        # Track files and commands
        if modified_files:
            self.state.all_modified_files.extend(modified_files)
        if executed_commands:
            self.state.all_executed_commands.extend(executed_commands)

        # Update token estimate
        if estimated_tokens:
            self.state.estimated_context_tokens = estimated_tokens

        logger.info(
            "[ENTERPRISE_ITERATION] Iteration %d: success=%s, failures=%d, tokens=%d",
            result.iteration_number,
            success,
            self.state.consecutive_failures,
            self.state.estimated_context_tokens,
        )

    async def create_checkpoint(
        self,
        context_summary: str,
        key_decisions: Optional[List[str]] = None,
        completed_tasks: Optional[List[str]] = None,
        pending_tasks: Optional[List[str]] = None,
        current_task: Optional[str] = None,
        project_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a checkpoint for resume capability."""
        if not self.checkpoint_callback:
            logger.warning("[ENTERPRISE_ITERATION] No checkpoint callback configured")
            return None

        checkpoint_id = f"chk_{self.config.enterprise_project_id or 'default'}_{self.state.iteration_count}"

        checkpoint = CheckpointData(
            checkpoint_id=checkpoint_id,
            iteration_number=self.state.iteration_count,
            timestamp=datetime.utcnow(),
            iteration_state=self.state.to_dict(),
            context_summary=context_summary,
            key_decisions=key_decisions or [],
            files_modified=list(set(self.state.all_modified_files)),
            commands_executed=self.state.all_executed_commands[-50:],  # Last 50
            completed_tasks=completed_tasks or [],
            pending_tasks=pending_tasks or [],
            current_task=current_task,
            project_state=project_state,
        )

        try:
            saved_id = await self.checkpoint_callback(checkpoint)
            self.state.record_checkpoint(saved_id)
            logger.info(
                "[ENTERPRISE_ITERATION] Created checkpoint %s at iteration %d",
                saved_id,
                self.state.iteration_count,
            )
            return saved_id
        except Exception as e:
            logger.error("[ENTERPRISE_ITERATION] Failed to save checkpoint: %s", e)
            return None

    async def summarize_context(self, current_context: str) -> Optional[str]:
        """Summarize context to reduce token usage."""
        if not self.summarize_callback:
            logger.warning("[ENTERPRISE_ITERATION] No summarize callback configured")
            return None

        try:
            summarized = await self.summarize_callback(current_context)

            # Estimate new token count (rough approximation)
            new_tokens = len(summarized.split()) * 1.3
            self.state.record_context_summarization(int(new_tokens))

            logger.info(
                "[ENTERPRISE_ITERATION] Summarized context, estimated tokens: %d",
                new_tokens,
            )
            return summarized
        except Exception as e:
            logger.error("[ENTERPRISE_ITERATION] Failed to summarize context: %s", e)
            return None

    def set_human_gate(self, gate_id: str):
        """Set a human checkpoint gate that requires approval."""
        self.state.set_gate(gate_id)
        logger.info("[ENTERPRISE_ITERATION] Human gate set: %s", gate_id)

    def clear_human_gate(self):
        """Clear the human gate after approval."""
        self.state.clear_gate()
        logger.info("[ENTERPRISE_ITERATION] Human gate cleared")

    def record_milestone(self, milestone_id: str):
        """Record completion of a milestone."""
        self.state.record_milestone(milestone_id)
        logger.info("[ENTERPRISE_ITERATION] Milestone completed: %s", milestone_id)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of iteration state."""
        return {
            "mode": self.config.mode.value,
            "max_iterations": self.config.max_iterations,
            "checkpoint_interval": self.config.checkpoint_interval,
            "enterprise_project_id": self.config.enterprise_project_id,
            **self.state.to_dict(),
        }

    def format_progress_message(self) -> str:
        """Format a progress message for the user."""
        if self.state.success:
            return (
                f"Task completed successfully after {self.state.iteration_count} "
                f"iteration(s) ({self.state.total_duration_ms / 1000:.1f}s total)"
            )

        if self.state.stopped_reason == "human_gate_pending":
            return (
                f"Paused at iteration {self.state.iteration_count} - "
                f"human checkpoint gate '{self.state.current_gate}' requires approval"
            )

        if self.state.stopped_reason == "max_iterations_reached":
            return (
                f"Stopped after {self.state.iteration_count} iterations (max reached). "
                "Task incomplete - may need manual intervention."
            )

        if self.state.stopped_reason == "max_consecutive_failures":
            return (
                f"Stopped after {self.state.consecutive_failures} consecutive failures. "
                "Please review errors and provide guidance."
            )

        if self.state.stopped_reason == "same_error_repeated":
            return (
                f"Stopped after {self.state.iteration_count} iterations - "
                "same error occurred twice. Different approach needed."
            )

        if self.state.stopped_reason == "no_progress":
            return (
                f"Stopped after {self.state.iteration_count} iterations - "
                "not making progress. Consider breaking into smaller tasks."
            )

        # Still running
        max_str = (
            f"/{self.config.max_iterations}"
            if self.config.max_iterations
            else " (unlimited)"
        )
        return (
            f"Iteration {self.state.iteration_count}{max_str} - "
            f"{len(self.state.checkpoints)} checkpoints created"
        )

    def get_resume_context(self) -> str:
        """Generate context string for resuming from current state."""
        context_parts = [
            f"Resuming enterprise task execution at iteration {self.state.iteration_count}",
            "",
            f"Progress: {self.state.iteration_count} iterations completed",
            f"Checkpoints: {len(self.state.checkpoints)}",
            f"Milestones completed: {', '.join(self.state.milestones_completed) or 'None yet'}",
        ]

        if self.state.all_modified_files:
            unique_files = list(set(self.state.all_modified_files))[:20]
            context_parts.extend(
                ["", "Files modified so far:", *[f"  - {f}" for f in unique_files]]
            )

        if self.state.test_counts:
            last_tests = self.state.test_counts[-1]
            context_parts.extend(
                [
                    "",
                    "Last test results:",
                    f"  Passed: {last_tests.get('passed', 0)}",
                    f"  Failed: {last_tests.get('failed', 0)}",
                ]
            )

        return "\n".join(context_parts)
