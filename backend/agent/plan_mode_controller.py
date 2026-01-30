"""
Plan Mode Controller - Manages end-to-end feature implementation with user control.

This enables the "Plan Mode" workflow where NAVI:
1. Analyzes the codebase to understand patterns
2. Creates an architectural plan for the feature
3. Presents the plan to the user (based on settings)
4. Executes the plan according to user's configured preferences
5. Runs tests and iterates until complete

Execution behavior is controlled by NaviSettings which users configure
through the VS Code settings panel.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from enum import Enum
import logging
import time
import json

if TYPE_CHECKING:
    from backend.agent.navi_settings import NaviSettings

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode for plan implementation."""

    FULLY_AUTONOMOUS = "fully_autonomous"  # No pauses, run end-to-end
    WITH_APPROVAL_GATES = "with_approval_gates"  # Pause for critical operations
    CUSTOM = "custom"  # User-provided custom instructions
    PLANNING = "planning"  # Still in planning phase


class PlanStepType(Enum):
    """Type of plan step - determines if approval is needed."""

    ANALYZE = "analyze"  # Read/search operations (no approval needed)
    CREATE_FILE = "create_file"  # Creating new files (approval in gated mode)
    MODIFY_FILE = "modify_file"  # Modifying existing files (approval in gated mode)
    DELETE_FILE = "delete_file"  # Deleting files (always needs approval)
    RUN_COMMAND = "run_command"  # Running shell commands (approval in gated mode)
    RUN_TESTS = "run_tests"  # Running tests (no approval needed)
    DEPLOY = "deploy"  # Deployment operations (always needs approval)


@dataclass
class PlanStep:
    """A single step in the implementation plan."""

    id: str
    description: str
    step_type: PlanStepType
    tool: str
    arguments: Dict[str, Any]
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    requires_approval: bool = False
    estimated_risk: str = "low"  # low, medium, high
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ImplementationPlan:
    """A complete implementation plan for a feature."""

    id: str
    title: str
    description: str
    steps: List[PlanStep]
    architecture_summary: str
    affected_files: List[str]
    estimated_steps: int
    created_at: float = field(default_factory=time.time)
    status: str = "draft"  # draft, approved, in_progress, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "steps": [
                {
                    "id": s.id,
                    "description": s.description,
                    "step_type": s.step_type.value,
                    "tool": s.tool,
                    "status": s.status,
                    "requires_approval": s.requires_approval,
                    "estimated_risk": s.estimated_risk,
                }
                for s in self.steps
            ],
            "architecture_summary": self.architecture_summary,
            "affected_files": self.affected_files,
            "estimated_steps": self.estimated_steps,
            "status": self.status,
        }


@dataclass
class PlanModeState:
    """State for plan mode execution."""

    plan: Optional[ImplementationPlan] = None
    execution_mode: ExecutionMode = ExecutionMode.PLANNING
    current_step_index: int = 0
    custom_instructions: Optional[str] = None
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    waiting_for_approval: bool = False
    pending_approval_step: Optional[str] = None
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 10

    def get_progress_percent(self) -> float:
        """Get completion percentage."""
        if not self.plan or not self.plan.steps:
            return 0.0
        return (self.completed_steps / len(self.plan.steps)) * 100

    def is_complete(self) -> bool:
        """Check if plan execution is complete."""
        if not self.plan:
            return False
        return self.completed_steps + self.skipped_steps >= len(self.plan.steps)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plan": self.plan.to_dict() if self.plan else None,
            "execution_mode": self.execution_mode.value,
            "current_step_index": self.current_step_index,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "progress_percent": self.get_progress_percent(),
            "waiting_for_approval": self.waiting_for_approval,
            "pending_approval_step": self.pending_approval_step,
            "is_complete": self.is_complete(),
        }


class PlanModeController:
    """
    Controller for managing plan mode execution.

    Handles the complete workflow:
    1. Generate architectural plan from user request
    2. Present plan (if settings require it)
    3. Execute plan according to user's configured settings
    4. Handle approval gates based on settings
    5. Run tests and iterate

    Behavior is controlled by NaviSettings from the settings panel.
    """

    # Map step types to operation names for settings lookup
    STEP_TYPE_TO_OPERATION = {
        PlanStepType.CREATE_FILE: "file_create",
        PlanStepType.MODIFY_FILE: "file_edit",
        PlanStepType.DELETE_FILE: "file_delete",
        PlanStepType.RUN_COMMAND: "run_command",
        PlanStepType.RUN_TESTS: "run_test",
        PlanStepType.DEPLOY: "deploy",
        PlanStepType.ANALYZE: None,  # Never needs approval
    }

    def __init__(self, settings: Optional["NaviSettings"] = None):
        self.state = PlanModeState()
        self._settings = settings

    @property
    def settings(self) -> "NaviSettings":
        """Get current settings, loading defaults if needed."""
        if self._settings is None:
            from backend.agent.navi_settings import NaviSettings

            self._settings = NaviSettings()
        return self._settings

    def set_settings(self, settings: "NaviSettings"):
        """Update the settings."""
        self._settings = settings
        if self.state.plan:
            self._update_approval_requirements()

    def set_execution_mode(self, mode: str, custom_instructions: Optional[str] = None):
        """Set the execution mode after user chooses."""
        try:
            self.state.execution_mode = ExecutionMode(mode)
        except ValueError:
            self.state.execution_mode = ExecutionMode.CUSTOM

        if mode == "custom" and custom_instructions:
            self.state.custom_instructions = custom_instructions

        if self.state.plan:
            self.state.plan.status = "approved"
            self._update_approval_requirements()

        logger.info(
            "[PLAN_MODE] Execution mode set to: %s", self.state.execution_mode.value
        )

    def _update_approval_requirements(self):
        """Update step approval requirements based on settings."""
        if not self.state.plan:
            return

        for step in self.state.plan.steps:
            step.requires_approval = self._step_requires_approval(step)

    def _step_requires_approval(self, step: PlanStep) -> bool:
        """Check if a step requires approval based on settings."""
        # Get the operation name for this step type
        operation = self.STEP_TYPE_TO_OPERATION.get(step.step_type)

        # Analyze steps never need approval
        if operation is None:
            return False

        # Check settings
        return self.settings.requires_approval_for(
            operation, context={"command": step.arguments.get("command", "")}
        )

    def set_plan(self, plan: ImplementationPlan):
        """Set the implementation plan."""
        self.state.plan = plan
        self.state.current_step_index = 0
        self.state.completed_steps = 0
        self.state.failed_steps = 0
        logger.info(
            "[PLAN_MODE] Plan set: %s with %d steps", plan.title, len(plan.steps)
        )

    def get_current_step(self) -> Optional[PlanStep]:
        """Get the current step to execute."""
        if not self.state.plan:
            return None
        if self.state.current_step_index >= len(self.state.plan.steps):
            return None
        return self.state.plan.steps[self.state.current_step_index]

    def needs_approval(self) -> bool:
        """Check if current step needs user approval."""
        step = self.get_current_step()
        if not step:
            return False
        return step.requires_approval

    def approve_step(self, step_id: str) -> bool:
        """Approve a pending step."""
        step = self.get_current_step()
        if step and step.id == step_id:
            self.state.waiting_for_approval = False
            self.state.pending_approval_step = None
            logger.info("[PLAN_MODE] Step approved: %s", step_id)
            return True
        return False

    def reject_step(self, step_id: str, reason: Optional[str] = None):
        """Reject a pending step (skip it)."""
        step = self.get_current_step()
        if step and step.id == step_id:
            step.status = "skipped"
            step.error = reason or "Rejected by user"
            self.state.skipped_steps += 1
            self.state.current_step_index += 1
            self.state.waiting_for_approval = False
            self.state.pending_approval_step = None
            logger.info("[PLAN_MODE] Step rejected: %s", step_id)

    def mark_step_completed(self, output: Optional[str] = None):
        """Mark current step as completed and move to next."""
        step = self.get_current_step()
        if step:
            step.status = "completed"
            step.output = output
            self.state.completed_steps += 1
            self.state.current_step_index += 1
            logger.info(
                "[PLAN_MODE] Step completed: %s (%d/%d)",
                step.id,
                self.state.completed_steps,
                len(self.state.plan.steps) if self.state.plan else 0,
            )

    def mark_step_failed(self, error: str):
        """Mark current step as failed."""
        step = self.get_current_step()
        if step:
            step.status = "failed"
            step.error = error
            self.state.failed_steps += 1
            logger.error("[PLAN_MODE] Step failed: %s - %s", step.id, error)

    def should_continue(self) -> bool:
        """Check if execution should continue."""
        if self.state.waiting_for_approval:
            return False
        if self.state.is_complete():
            return False
        if self.state.iteration_count >= self.state.max_iterations:
            logger.warning("[PLAN_MODE] Max iterations reached")
            return False
        return True

    def get_status_message(self) -> str:
        """Get human-readable status message."""
        if not self.state.plan:
            return "No plan created yet."

        progress = self.state.get_progress_percent()

        if self.state.waiting_for_approval:
            step = self.get_current_step()
            return (
                f"**Waiting for approval** ({progress:.0f}% complete)\n\n"
                f"Step: {step.description if step else 'Unknown'}\n"
                f"Type: {step.step_type.value if step else 'Unknown'}\n"
                f"Risk: {step.estimated_risk if step else 'Unknown'}"
            )

        if self.state.is_complete():
            if self.state.failed_steps > 0:
                return (
                    f"**Plan completed with issues** (100%)\n\n"
                    f"- Completed: {self.state.completed_steps}\n"
                    f"- Failed: {self.state.failed_steps}\n"
                    f"- Skipped: {self.state.skipped_steps}"
                )
            return (
                f"**Plan completed successfully!** ({self.state.completed_steps} steps)"
            )

        return (
            f"**Executing plan** ({progress:.0f}% complete)\n\n"
            f"Step {self.state.current_step_index + 1}/{len(self.state.plan.steps)}"
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            "status": self.state.plan.status if self.state.plan else "no_plan",
            "execution_mode": self.state.execution_mode.value,
            "progress_percent": self.state.get_progress_percent(),
            "completed_steps": self.state.completed_steps,
            "failed_steps": self.state.failed_steps,
            "skipped_steps": self.state.skipped_steps,
            "total_steps": len(self.state.plan.steps) if self.state.plan else 0,
            "is_complete": self.state.is_complete(),
            "waiting_for_approval": self.state.waiting_for_approval,
            "test_results": self.state.test_results,
        }


def generate_execution_options_message(plan: ImplementationPlan) -> str:
    """
    Generate the message showing plan and execution options to user.

    Args:
        plan: The generated implementation plan

    Returns:
        Formatted message for display in UI
    """
    # Build plan summary
    steps_summary = []
    for i, step in enumerate(plan.steps[:10], 1):  # Show first 10 steps
        risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
            step.estimated_risk, "⚪"
        )
        steps_summary.append(f"  {i}. {risk_emoji} {step.description}")

    if len(plan.steps) > 10:
        steps_summary.append(f"  ... and {len(plan.steps) - 10} more steps")

    steps_text = "\n".join(steps_summary)

    # Build affected files list
    files_text = "\n".join([f"  - {f}" for f in plan.affected_files[:10]])
    if len(plan.affected_files) > 10:
        files_text += f"\n  ... and {len(plan.affected_files) - 10} more files"

    message = f"""## Implementation Plan: {plan.title}

### Overview
{plan.description}

### Architecture
{plan.architecture_summary}

### Implementation Steps ({len(plan.steps)} total)
{steps_text}

### Affected Files
{files_text}

---

## How would you like to proceed?

**Choose an execution mode:**

1. **🚀 Fully Autonomous** - NAVI will implement the entire plan automatically without pauses. Best for trusted, well-defined tasks.

2. **🔐 With Approval Gates** - NAVI will pause before critical operations (file modifications, commands) and ask for your approval. Recommended for most tasks.

3. **✍️ Custom Instructions** - Provide specific instructions for how NAVI should proceed.

Please respond with:
- `1` or `autonomous` - for fully autonomous execution
- `2` or `gated` - for execution with approval gates
- `3` or `custom: <your instructions>` - for custom execution
"""

    return message


def parse_execution_choice(user_response: str) -> tuple[str, Optional[str]]:
    """
    Parse user's execution mode choice.

    Args:
        user_response: User's response text

    Returns:
        Tuple of (execution_mode, custom_instructions or None)
    """
    response = user_response.strip().lower()

    # Check for option 1 (autonomous)
    if response in ("1", "autonomous", "fully autonomous", "auto"):
        return ("fully_autonomous", None)

    # Check for option 2 (gated)
    if response in ("2", "gated", "with approval", "approval gates", "approval"):
        return ("with_approval_gates", None)

    # Check for option 3 (custom)
    if response.startswith("3") or response.startswith("custom"):
        # Extract custom instructions
        if ":" in response:
            instructions = response.split(":", 1)[1].strip()
        else:
            instructions = response.replace("3", "").replace("custom", "").strip()
        return ("custom", instructions or "Follow user guidance")

    # Default to gated mode for safety
    return ("with_approval_gates", None)


def create_approval_request_message(step: PlanStep) -> str:
    """
    Create an approval request message for a step.

    Args:
        step: The step requiring approval

    Returns:
        Formatted approval request message
    """
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(step.estimated_risk, "⚪")

    message = f"""## Approval Required {risk_emoji}

**Step:** {step.description}
**Type:** {step.step_type.value}
**Risk Level:** {step.estimated_risk}
**Tool:** {step.tool}

**Details:**
```json
{json.dumps(step.arguments, indent=2, default=str)}
```

---

**Options:**
- `approve` or `yes` - Proceed with this step
- `reject` or `no` - Skip this step
- `modify: <instructions>` - Modify how this step is executed
"""

    return message
