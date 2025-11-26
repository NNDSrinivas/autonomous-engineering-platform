from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from .intent_schema import NaviIntent
from .orchestrator import PlannedStep


@dataclass
class StepResult:
    step_id: str
    ok: bool
    output: Any
    error: str | None = None


class ToolExecutor(Protocol):
    """
    Interface for NAVI tool execution engine.
    """

    async def execute_step(
        self,
        step: PlannedStep,
        *,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> StepResult:
        ...


class SimpleToolExecutor(ToolExecutor):
    """
    Minimal, safe executor.

    For now it just echoes the step and context; later we replace this with
    real tools (code search, git, tests, etc).
    """

    async def execute_step(
        self,
        step: PlannedStep,
        *,
        intent: NaviIntent,
        context: Dict[str, Any],
    ) -> StepResult:
        try:
            output = {
                "tool": step.tool,
                "arguments": step.arguments,
                "intent_kind": intent.kind.value,
            }
            return StepResult(
                step_id=step.id,
                ok=True,
                output=output,
                error=None,
            )
        except Exception as e:
            return StepResult(
                step_id=step.id,
                ok=False,
                output=None,
                error=str(e),
            )