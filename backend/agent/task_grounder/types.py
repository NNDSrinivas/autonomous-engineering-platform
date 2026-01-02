"""
Task Grounding Types

Clean, deterministic type definitions for grounding user intents into executable tasks.
This eliminates the need for LLM guessing and provides structured inputs to the planner.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel


class Diagnostic(BaseModel):
    """Represents a code diagnostic (error/warning)"""
    file: str
    message: str
    severity: Literal["error", "warning", "info"]
    code: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    range: Optional[Dict[str, Any]] = None


class Clarification(BaseModel):
    """Request for user clarification when grounding is ambiguous"""
    message: str
    options: List[str]
    context: Dict[str, Any]


class GroundedTask(BaseModel):
    """A fully grounded task ready for planner execution"""
    intent: Literal["FIX_PROBLEMS", "DEPLOY"]  # Extensible for future intents
    scope: str  # "workspace", "file", "project", etc.
    target: str  # "diagnostics", "tests", "deployment", etc.
    inputs: Dict[str, Any]  # Structured data for the task
    requires_approval: bool = True
    confidence: float = 1.0
    metadata: Dict[str, Any] = {}


class FixProblemsTask(GroundedTask):
    """Specific grounded task for fixing problems"""
    intent: Literal["FIX_PROBLEMS"] = "FIX_PROBLEMS"
    scope: Literal["workspace"] = "workspace"
    target: Literal["diagnostics"] = "diagnostics"
    inputs: Dict[str, Any]  # Contains diagnostics and affected_files


class DeployTask(GroundedTask):
    """Specific grounded task for deployment"""
    intent: Literal["DEPLOY"] = "DEPLOY"
    scope: Literal["repo"] = "repo"
    target: Literal["deployment"] = "deployment"
    inputs: Dict[str, Any]  # Contains deploy method, target environment, etc.


class GroundingResult(BaseModel):
    """Result of task grounding attempt"""
    type: Literal["ready", "clarification", "rejected"]
    task: Optional[GroundedTask] = None
    clarification: Optional[Clarification] = None
    reason: Optional[str] = None
