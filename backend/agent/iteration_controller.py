"""
Iteration Controller - Manages iterative planning loops for NAVI.

This enables "run until tests pass" mode where NAVI can:
1. Execute a plan
2. Run tests
3. Analyze failures
4. Generate fix plan
5. Repeat until success or max iterations

The iteration controller tracks state across iterations and prevents
infinite loops by detecting repeated errors.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import logging
import hashlib

logger = logging.getLogger(__name__)


class IterationMode(Enum):
    """Iteration mode for agent execution."""

    ONE_SHOT = "one_shot"  # Single execution (default)
    UNTIL_TESTS_PASS = "until_tests_pass"  # Iterate until all tests pass
    UNTIL_NO_ERRORS = "until_no_errors"  # Iterate until no lint/type errors
    MAX_ITERATIONS = "max_iterations"  # Run a fixed number of iterations


@dataclass
class IterationConfig:
    """Configuration for iterative execution."""

    mode: IterationMode = IterationMode.ONE_SHOT
    max_iterations: int = (
        5  # Conservative default; increase explicitly for complex tasks
    )
    stop_on_same_error: bool = True  # Stop if same error appears twice
    stop_on_no_progress: bool = True  # Stop if test count doesn't improve
    timeout_per_iteration_ms: int = 60000  # 1 minute per iteration

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "IterationConfig":
        """Create config from dictionary."""
        mode_str = config.get("mode", "one_shot")
        try:
            mode = IterationMode(mode_str)
        except ValueError:
            mode = IterationMode.ONE_SHOT

        return cls(
            mode=mode,
            max_iterations=config.get("max_iterations", 5),
            stop_on_same_error=config.get("stop_on_same_error", True),
            stop_on_no_progress=config.get("stop_on_no_progress", True),
            timeout_per_iteration_ms=config.get("timeout_per_iteration_ms", 60000),
        )


@dataclass
class IterationResult:
    """Result from a single iteration."""

    iteration_number: int
    success: bool
    plan_executed: bool
    test_results: Optional[Dict[str, Any]] = None
    debug_analysis: Optional[Dict[str, Any]] = None
    error_hash: Optional[str] = None  # Hash of error for deduplication
    duration_ms: int = 0


@dataclass
class IterationState:
    """State tracked across iterations."""

    iteration_count: int = 0
    errors_seen: List[str] = field(default_factory=list)  # Error hashes
    test_counts: List[Dict[str, int]] = field(
        default_factory=list
    )  # Test results per iteration
    results: List[IterationResult] = field(default_factory=list)
    success: bool = False
    stopped_reason: Optional[str] = None

    def should_continue(self, config: IterationConfig) -> bool:
        """Determine if iteration should continue."""
        # Already succeeded
        if self.success:
            logger.info("[ITERATION] Stopping: success achieved")
            return False

        # Max iterations reached
        if self.iteration_count >= config.max_iterations:
            self.stopped_reason = "max_iterations_reached"
            logger.info(
                "[ITERATION] Stopping: max iterations (%d) reached",
                config.max_iterations,
            )
            return False

        # Same error twice in a row
        if config.stop_on_same_error and len(self.errors_seen) >= 2:
            if self.errors_seen[-1] == self.errors_seen[-2]:
                self.stopped_reason = "same_error_repeated"
                logger.info("[ITERATION] Stopping: same error repeated")
                return False

        # No progress in test counts
        if config.stop_on_no_progress and len(self.test_counts) >= 2:
            current = self.test_counts[-1]
            previous = self.test_counts[-2]
            # If failed count isn't decreasing, we're not making progress
            if current.get("failed", 0) >= previous.get("failed", 0):
                self.stopped_reason = "no_progress"
                logger.info("[ITERATION] Stopping: no progress in test results")
                return False

        return True

    def record_result(self, result: IterationResult):
        """Record the result of an iteration."""
        self.results.append(result)
        self.iteration_count += 1

        if result.success:
            self.success = True

        if result.error_hash:
            self.errors_seen.append(result.error_hash)

        if result.test_results:
            self.test_counts.append(
                {
                    "total": result.test_results.get("total", 0),
                    "passed": result.test_results.get("passed", 0),
                    "failed": result.test_results.get("failed", 0),
                }
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "iteration_count": self.iteration_count,
            "success": self.success,
            "stopped_reason": self.stopped_reason,
            "test_counts": self.test_counts,
            "errors_seen_count": len(self.errors_seen),
            "results": [
                {
                    "iteration": r.iteration_number,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "test_passed": (
                        r.test_results.get("passed", 0) if r.test_results else 0
                    ),
                    "test_failed": (
                        r.test_results.get("failed", 0) if r.test_results else 0
                    ),
                }
                for r in self.results
            ],
        }


class IterationController:
    """
    Controller for managing iterative plan execution.

    Handles the loop logic for "run until tests pass" mode:
    1. Execute plan
    2. Run tests
    3. If tests fail, analyze errors
    4. Generate fix plan
    5. Repeat
    """

    def __init__(self, config: Optional[IterationConfig] = None):
        self.config = config or IterationConfig()
        self.state = IterationState()

    @classmethod
    def create(
        cls, iteration_mode: str = "one_shot", **kwargs
    ) -> "IterationController":
        """Create controller from mode string and options."""
        config_dict = {"mode": iteration_mode, **kwargs}
        config = IterationConfig.from_dict(config_dict)
        return cls(config)

    def should_iterate(self) -> bool:
        """Check if we should continue iterating."""
        if self.config.mode == IterationMode.ONE_SHOT:
            return False
        return self.state.should_continue(self.config)

    def record_iteration(
        self,
        success: bool,
        test_results: Optional[Dict[str, Any]] = None,
        debug_analysis: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0,
    ):
        """Record the result of an iteration."""
        # Generate error hash for deduplication
        error_hash = None
        if test_results and not success:
            failed_tests = test_results.get("failed_tests", [])
            if failed_tests:
                # Hash based on test names and error messages
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

        self.state.record_result(result)
        logger.info(
            "[ITERATION] Recorded iteration %d: success=%s, error_hash=%s",
            result.iteration_number,
            success,
            error_hash,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of iteration results."""
        return {
            "mode": self.config.mode.value,
            "max_iterations": self.config.max_iterations,
            **self.state.to_dict(),
        }

    def format_progress_message(self) -> str:
        """Format a progress message for the user."""
        if self.state.success:
            return f"All tests passed after {self.state.iteration_count} iteration(s)."

        if self.state.stopped_reason == "max_iterations_reached":
            return f"Stopped after {self.state.iteration_count} iterations (max reached). Some tests still failing."

        if self.state.stopped_reason == "same_error_repeated":
            return f"Stopped after {self.state.iteration_count} iterations - same error occurred twice. Manual intervention needed."

        if self.state.stopped_reason == "no_progress":
            return f"Stopped after {self.state.iteration_count} iterations - not making progress on test failures."

        # Still running
        return f"Iteration {self.state.iteration_count}/{self.config.max_iterations} completed..."


def create_fix_context(
    original_message: str,
    test_results: Dict[str, Any],
    debug_analysis: Optional[Dict[str, Any]] = None,
    iteration_count: int = 1,
) -> Dict[str, Any]:
    """
    Create context for generating a fix plan.

    This is used to provide the planner with information about what failed
    so it can generate an appropriate fix.

    Args:
        original_message: The user's original request
        test_results: Test results from _verify_with_tests
        debug_analysis: Debug analysis from _analyze_errors_with_debugger
        iteration_count: Current iteration number

    Returns:
        Context dict for the planner
    """
    failed_tests = test_results.get("failed_tests", [])

    # Build failure summary
    failure_summary = []
    for ft in failed_tests[:5]:
        summary = f"- {ft.get('name', 'unknown')}"
        if ft.get("error_message"):
            summary += f": {ft['error_message'][:200]}"
        if ft.get("file_path") and ft.get("line_number"):
            summary += f" ({ft['file_path']}:{ft['line_number']})"
        failure_summary.append(summary)

    # Build fix suggestions from debug analysis
    fix_hints = []
    if debug_analysis:
        for error in debug_analysis.get("errors", [])[:3]:
            for suggestion in error.get("suggestions", [])[:2]:
                fix_hints.append(suggestion)

        for fix in debug_analysis.get("auto_fixes", [])[:2]:
            fix_hints.append(f"Try: {fix.get('command', '')}")

    return {
        "original_request": original_message,
        "iteration": iteration_count,
        "test_results": {
            "total": test_results.get("total", 0),
            "passed": test_results.get("passed", 0),
            "failed": test_results.get("failed", 0),
        },
        "failure_summary": "\n".join(failure_summary),
        "fix_hints": fix_hints,
        "instruction": (
            f"Fix these test failures. This is iteration {iteration_count}. "
            "Do NOT repeat approaches that already failed. "
            "Focus on the specific errors and apply targeted fixes."
        ),
    }
