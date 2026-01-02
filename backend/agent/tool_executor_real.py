from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from .intent_schema import NaviIntent
from ..orchestrator import PlannedStep
from .tool_executor import execute_tool
from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


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
    ) -> StepResult: ...


class RealToolExecutor(ToolExecutor):
    """
    Production tool executor that integrates with the actual NAVI tool system.
    
    This executor bridges the orchestrator with the real tool implementations
    (file operations, command execution, etc.)
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    async def execute_step(
        self,
        step: PlannedStep,
        *args,  # Handle both positional and keyword arguments
        intent: Optional[NaviIntent] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> StepResult:
        """Execute a planned step using real NAVI tools."""
        try:
            # Handle different calling patterns from orchestrator
            if args:
                # Called with positional args: step, workspace_root, intent, context
                if len(args) >= 3:
                    workspace_root, intent_arg, context_arg = args[0], args[1], args[2]
                    intent = intent or intent_arg
                    context = context or context_arg
                elif len(args) >= 2:
                    workspace_root, context_arg = args[0], args[1]  
                    context = context or context_arg
                elif len(args) >= 1:
                    workspace_root = args[0]
                    
                # Ensure context has workspace_root if provided
                if context is None:
                    context = {}
                if 'workspace_root' not in context and 'workspace_root' in locals():
                    context['workspace_root'] = workspace_root
            
            # Default context if not provided
            if context is None:
                context = {}
            
            logger.info(f"[RealToolExecutor] Executing step {step.id}: {step.tool}")
            
            # Extract user context
            user_id = context.get("user_id", "default_user")
            workspace = context.get("workspace", {})
            attachments = context.get("attachments", [])
            
            # Execute the actual tool
            tool_result = await execute_tool(
                user_id=user_id,
                tool_name=step.tool,
                args=step.arguments,
                db=self.db,
                attachments=attachments,
                workspace=workspace,
            )
            
            # Check if tool execution was successful
            success = tool_result.get("success", True)  # Default to True if not specified
            
            # Some tools don't have explicit success field, check for error
            if "error" in tool_result and tool_result["error"]:
                success = False
                
            return StepResult(
                step_id=step.id,
                ok=success,
                output=tool_result,
                error=tool_result.get("error"),
            )
            
        except Exception as e:
            logger.error(f"[RealToolExecutor] Step {step.id} failed: {e}")
            return StepResult(
                step_id=step.id,
                ok=False,
                output=None,
                error=str(e),
            )


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
            if step.tool == "context.present_packet":
                packet = context.get("context_packet")
                if not packet:
                    return StepResult(
                        step_id=step.id,
                        ok=False,
                        output=None,
                        error="No context packet provided",
                    )
                output = {
                    "tool": step.tool,
                    "packet": packet,
                    "intent_kind": intent.kind.value,
                }
            else:
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
