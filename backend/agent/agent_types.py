"""
Agent Types - Structured types for NAVI agent runs

Defines the data structures for agent execution that enable Copilot-style
UI feedback showing what NAVI is doing step-by-step.
"""

from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

AgentStepStatus = Literal["pending", "running", "done", "blocked"]


class AgentStep(BaseModel):
    """
    A single step in an agent run.
    
    Examples:
    - "Understand your request"
    - "Gather org context from Jira/Slack"
    - "Plan what to do"
    - "Propose or apply code changes"
    """
    id: str = Field(..., description="Unique step identifier")
    label: str = Field(..., description="Human-readable step description")
    status: AgentStepStatus = Field(default="pending", description="Current step status")
    detail: Optional[str] = Field(None, description="Additional step details or results")


class AgentRunSummary(BaseModel):
    """
    Summary of an agent run showing all steps and overall status.
    
    This structure is sent to the VS Code extension to render a
    Copilot-style "Agent Run" card showing NAVI's work progress.
    """
    id: str = Field(..., description="Unique run identifier")
    title: str = Field(..., description="Run title (e.g., 'NAVI Agent Run')")
    status: Literal["planning", "executing", "completed", "failed"] = Field(
        default="planning",
        description="Overall run status"
    )
    steps: List[AgentStep] = Field(default_factory=list, description="List of execution steps")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (mode, timing, context sources, etc)"
    )
