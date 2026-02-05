# backend/api/navi.py
# pyright: reportGeneralTypeIssues=false

"""
NAVI Chat API (agent OS v2)

Main chat endpoint used by the VS Code extension:

  POST /api/navi/chat

Payload (from extension):
{
  "message": "hi could you list the jira tasks assigned to me?",
  "model": "gpt-5.1",
  "mode": "agent-full",
  "attachments": [],
  "user_id": "default_user"
}

This file:

- Calls the NAVI agent loop (`run_agent_loop`) for every message.
- Maps `reply` -> `content` so the extension can render it.
- Returns `actions` and a lightweight `agentRun` for the Workspace plan card.
"""

from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE
import json
import random
import logging
import os
import re
import time
from asyncio.subprocess import STDOUT
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Tuple, no_type_check

from dotenv import load_dotenv
from openai import AsyncOpenAI

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.agent.agent_loop import run_agent_loop
from backend.agent.planner_v3 import PlannerV3
from backend.agent.tool_executor import execute_tool_with_sources
from backend.agent.intent_schema import (
    IntentFamily,
    IntentKind,
    IntentSource,
    IntentPriority,
    NaviIntent,
)
from backend.services.git_service import GitService

# Conversation memory for cross-session persistence
from backend.services.memory.conversation_memory import ConversationMemoryService

# NOTE: ProjectAnalyzer is in backend/services/navi_brain.py
# The /api/navi/chat endpoint in chat.py uses navi_brain.py's implementation


# Phase 4.1.2: Planner Engine Data Models
class ContextPack(BaseModel):
    """Context information collected by extension for planning"""

    workspace: Dict[str, Any] = Field(default_factory=dict)
    repo: Optional[Dict[str, Any]] = None
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    active_file: Optional[Dict[str, Any]] = None
    selected_text: Optional[str] = None


class PlanStep(BaseModel):
    """Individual step in a plan"""

    id: str
    title: str
    rationale: Optional[str] = None
    requires_approval: bool = False
    tool: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    verify: List[str] = Field(default_factory=list)  # verification rules
    status: Literal["pending", "active", "completed", "failed", "skipped"] = "pending"


class Plan(BaseModel):
    """Multi-step execution plan"""

    id: str
    goal: str
    steps: List[PlanStep]
    requires_approval: bool = False
    confidence: float = 0.0
    reasoning: Optional[str] = None


class RunState(BaseModel):
    """Complete state of a NAVI run"""

    run_id: str
    user_message: str
    intent: NaviIntent
    context: ContextPack
    plan: Optional[Plan] = None
    current_step: int = 0
    status: Literal["idle", "planning", "executing", "verifying", "done", "failed"] = (
        "idle"
    )
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class ToolRequest(BaseModel):
    """Request for tool execution"""

    run_id: str
    request_id: str
    tool: str
    args: Dict[str, Any]
    approval: Dict[str, Any]


class ToolResult(BaseModel):
    """Result of tool execution"""

    run_id: str
    request_id: str
    tool: str
    ok: bool
    output: Any
    error: Optional[str] = None


# Global run state storage (in-memory for now)
active_runs: Dict[str, RunState] = {}

logger = logging.getLogger(__name__)


# Model alias resolution - maps fake/future model IDs to real valid models
MODEL_ALIASES: Dict[str, Dict[str, str]] = {
    # Special aliases for auto/recommended routing
    "recommended": {"provider": "openai", "model": "gpt-4o"},
    "auto": {"provider": "openai", "model": "gpt-4o"},
    "auto/recommended": {"provider": "openai", "model": "gpt-4o"},
    # OpenAI models - map fake/future model IDs to real valid models
    "openai/gpt-5": {"provider": "openai", "model": "gpt-4o"},
    "openai/gpt-5-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "openai/gpt-5-nano": {"provider": "openai", "model": "gpt-4o-mini"},
    "openai/gpt-4.1": {"provider": "openai", "model": "gpt-4o"},
    "openai/gpt-4.1-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-5.1": {"provider": "openai", "model": "gpt-4o"},
    "gpt-5.0": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4.1": {"provider": "openai", "model": "gpt-4o"},
    "gpt-4.1-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    # Direct model IDs for frontend llmRouter compatibility
    "openai/gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "openai/gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    # Anthropic models
    "anthropic/claude-sonnet-4": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
    },
    "anthropic/claude-opus-4": {
        "provider": "anthropic",
        "model": "claude-opus-4-20250514",
    },
    # Google models
    "google/gemini-2.5-pro": {"provider": "google", "model": "gemini-2.0-flash-exp"},
    "google/gemini-2.5-flash": {"provider": "google", "model": "gemini-2.0-flash-exp"},
}


def _resolve_model(model: Optional[str]) -> str:
    """Resolve model alias to actual model ID."""
    if not model:
        return "gpt-4o-mini"  # Default model

    # Check if it's an alias
    if model in MODEL_ALIASES:
        return MODEL_ALIASES[model]["model"]

    # If it's a provider/model format, check the full path
    if "/" in model:
        if model in MODEL_ALIASES:
            return MODEL_ALIASES[model]["model"]
        # Extract just the model part
        _, model_name = model.split("/", 1)
        if model_name in MODEL_ALIASES:
            return MODEL_ALIASES[model_name]["model"]
        return model_name  # Return the model part

    return model  # Return as-is if not an alias


router = APIRouter(prefix="/api/navi", tags=["navi-extension"])
agent_router = APIRouter(prefix="/api/agent", tags=["agent-classify"])


class ProgressTracker:
    """Simple progress tracker for user status updates"""

    def __init__(self):
        self.steps = []
        self.current_status = "Processing request..."

    def update_status(self, status: str):
        self.current_status = status
        logger.info(f"[NAVI-PROGRESS] {status}")

    def complete_step(self, step: str):
        self.steps.append(step)
        logger.info(f"[NAVI-PROGRESS] ✅ {step}")

    def get_status(self) -> Dict[str, Any]:
        return {"status": self.current_status, "progress_steps": self.steps.copy()}


# Feature-flag: still allow running without OpenAI, but in degraded mode
# Load environment variables from .env so OPENAI_API_KEY is available in local dev.
load_dotenv(dotenv_path=".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ENABLED = bool(OPENAI_API_KEY)

# Debug log to confirm whether OpenAI is enabled at import time
print(
    "NAVI OpenAI status:",
    "ENABLED" if OPENAI_ENABLED else "DISABLED",
    "| API key set:",
    bool(OPENAI_API_KEY),
)
if not OPENAI_ENABLED:
    logger.warning("OPENAI_API_KEY is not set; NAVI agent will run in degraded mode.")

openai_client: Optional[AsyncOpenAI] = None
if OPENAI_ENABLED:
    try:
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        logger.error("Failed to initialize OpenAI client: %s", e, exc_info=True)
        openai_client = None

# Initialize PlannerV3 for fast-path routing
planner_v3 = PlannerV3()


@agent_router.post("/classify")
async def classify_intent_simple(request: Dict[str, Any]):
    """Classification endpoint that redirects to NAVI intent classification"""
    # Support multiple field names for message content
    message = (
        request.get("message")
        or request.get("text")
        or request.get("content")
        or request.get("prompt")
        or request.get("input")
        or ""
    )

    # Ensure message is a string
    if not isinstance(message, str):
        message = str(message) if message else ""

    # Use the same intent classification logic as /api/navi/intent
    intent_map = {
        "fix": ["error", "bug", "issue", "problem", "broken", "crash", "fail"],
        "code": ["implement", "feature", "add", "create", "build", "develop", "code"],
        "workspace": [
            "repo",
            "project",
            "workspace",
            "directory",
            "structure",
            "files",
        ],
        "git": ["commit", "branch", "merge", "pull", "push", "git", "version"],
        "docs": ["document", "readme", "explain", "describe", "help", "guide"],
    }

    message_lower = message.lower().strip()
    if not message_lower:
        return {"intent": "general"}

    for intent, keywords in intent_map.items():
        if any(keyword in message_lower for keyword in keywords):
            return {"intent": intent}

    return {"intent": "general"}


# Real repo scanning configuration
REPO_EXPLAIN_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".next",
    ".turbo",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".DS_Store",
    ".venv",
    "venv",
    "coverage",
    "logs",
}

REPO_EXPLAIN_IGNORE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".map",
    ".log",
    ".lock",
    ".zip",
    ".tar",
    ".gz",
    ".mp4",
    ".mov",
    ".mp3",
}

REPO_EXPLAIN_KEY_FILENAMES = {
    "package.json",
    "README.md",
    "README",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "tsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "vite.config.ts",
    "vite.config.js",
}

# Legacy excluded dirs (kept for backward compatibility)
_REPO_SUMMARY_EXCLUDED_DIRS = REPO_EXPLAIN_IGNORE_DIRS

# Jira keywords for fast-path routing
JIRA_KEYWORDS = (
    "jira",
    "ticket",
    "tickets",
    "issue",
    "issues",
    "story",
    "stories",
    "assigned",
)
ME_KEYWORDS = (
    "assigned to me",
    "my tickets",
    "my issues",
    "my tasks",
    "assigned for me",
    "my jira",
)
WORK_KEYWORDS = (
    "jira",
    "ticket",
    "issue",
    "pr",
    "pull request",
    "code",
    "build",
    "test",
    "plan",
    "doc",
    "repo",
)


# Phase 4.1.2: Intent Classification Endpoint
@router.post("/intent")
async def classify_intent(
    message: str, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classify user message into structured intent.
    Returns IntentKind + confidence + metadata.
    """
    try:
        progress = ProgressTracker()
        progress.update_status("Classifying user intent...")

        # Simple rule-based classification for now
        message_lower = message.lower().strip()

        # Diagnostic/error fixing intents
        if any(
            word in message_lower
            for word in [
                "error",
                "errors",
                "problem",
                "problems",
                "fix",
                "bug",
                "issue",
            ]
        ):
            if "problems tab" in message_lower or "diagnostics" in message_lower:
                intent_kind = IntentKind.FIX_BUG
                family = IntentFamily.ENGINEERING
                confidence = 0.9
            elif "file" in message_lower:
                intent_kind = IntentKind.MODIFY_CODE
                family = IntentFamily.ENGINEERING
                confidence = 0.8
            else:
                intent_kind = IntentKind.FIX_BUG
                family = IntentFamily.ENGINEERING
                confidence = 0.7

        # Repository inspection intents
        elif any(
            word in message_lower
            for word in ["repo", "repository", "explain", "what", "overview"]
        ):
            intent_kind = IntentKind.INSPECT_REPO
            family = IntentFamily.ENGINEERING
            confidence = 0.85

        # Build/run intents
        elif any(
            word in message_lower
            for word in ["build", "run", "start", "compile", "test"]
        ):
            if "test" in message_lower:
                intent_kind = IntentKind.RUN_TESTS
            else:
                intent_kind = IntentKind.RUN_BUILD
            family = IntentFamily.ENGINEERING
            confidence = 0.8

        # Feature implementation intents
        elif any(
            word in message_lower for word in ["implement", "feature", "add", "create"]
        ):
            intent_kind = IntentKind.IMPLEMENT_FEATURE
            family = IntentFamily.ENGINEERING
            confidence = 0.75

        # JIRA/ticket intents
        elif any(
            word in message_lower
            for word in ["jira", "ticket", "issue", "task", "assigned"]
        ):
            intent_kind = IntentKind.LIST_MY_ITEMS
            family = IntentFamily.PROJECT_MANAGEMENT
            confidence = 0.8

        else:
            # Default to general explanation
            intent_kind = IntentKind.EXPLAIN_CODE
            family = IntentFamily.ENGINEERING
            confidence = 0.5

        intent = NaviIntent(
            family=family,
            kind=intent_kind,
            priority=IntentPriority.NORMAL,
            requires_approval=False,
            target=None,
            parameters={},
            confidence=confidence,
            raw_text=message,
        )

        return {
            "success": True,
            "intent": intent.dict(),
            "reasoning": f"Classified as {intent_kind} based on keywords and context",
        }

    except Exception as e:
        logger.error(f"Intent classification error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "intent": None}


class PlanRequest(BaseModel):
    message: str
    intent: Dict[str, Any]
    context: Dict[str, Any]


# Phase 4.1.2: Plan Generation Endpoint
@router.post("/plan")
async def generate_plan(request: PlanRequest) -> Dict[str, Any]:
    """
    Generate multi-step execution plan based on intent and context.
    Uses strict planner contract for deterministic plans.
    """
    try:
        from backend.planner import run_planner, Intent, PlannerRequest

        progress = ProgressTracker()
        progress.update_status("Generating execution plan...")

        intent_kind = request.intent.get("kind")
        run_id = f"plan_{int(time.time())}_{random.randint(1000, 9999)}"

        # Map intent to strict enum
        try:
            if intent_kind == "fix_diagnostics":
                planner_intent = Intent.FIX_PROBLEMS
            else:
                # For now, only fix_diagnostics is supported in Phase 4.1 Step 1
                return {
                    "success": False,
                    "error": f"Intent '{intent_kind}' not supported in Phase 4.1. Currently only fix_diagnostics is implemented.",
                    "plan": None,
                    "session_id": None,
                }

            # Create strict planner request
            planner_request = PlannerRequest(
                intent=planner_intent,
                context={
                    "workspaceRoot": request.context.get("workspace", {}).get(
                        "root", ""
                    ),
                    "userMessage": request.message,
                    "diagnostics": request.context.get("diagnostics", []),
                    "active_file": request.context.get("active_file"),
                },
            )

            # Run strict planner
            planner_response = run_planner(planner_request)

            # Convert planner response to API format
            plan = {
                "goal": f"Execute {planner_response.intent.value} plan",
                "confidence": 1.0,  # Deterministic plans have 100% confidence
                "steps": [
                    {
                        "id": f"step_{i+1}",
                        "title": step.tool,
                        "rationale": step.reason,
                        "tool": step.tool,
                        "status": "pending",
                        "requires_approval": False,  # Phase 4.1 Step 1: no approval needed
                        "verify": [],
                    }
                    for i, step in enumerate(planner_response.steps)
                ],
                "requires_approval": False,
            }

            # Register the plan in active_runs so /next can find it
            plan_obj = Plan(
                id=run_id,
                goal=plan["goal"],
                steps=[
                    PlanStep(
                        id=step["id"],
                        title=step["title"],
                        rationale=step.get("rationale"),
                        tool=step.get("tool"),
                        requires_approval=step.get("requires_approval", False),
                        verify=step.get("verify", []),
                        status=step.get("status", "pending"),
                    )
                    for step in plan["steps"]
                ],
                requires_approval=plan.get("requires_approval", False),
                confidence=plan.get("confidence", 1.0),
                reasoning=f"Generated deterministic {planner_response.intent.value} plan",
            )

            # Create RunState and register it
            run_state = RunState(
                run_id=run_id,
                user_message=request.message,
                intent=NaviIntent(
                    kind=intent_kind, confidence=1.0, raw_text=request.message
                ),
                context=ContextPack(
                    workspaceRoot=request.context.get("workspace", {}).get("root", ""),
                    errors=[],
                    diagnostics=request.context.get("diagnostics", []),
                ),
                plan=plan_obj,
                current_step=0,
                status="executing",
            )
            active_runs[run_id] = run_state
            logger.info(f"[NAVI] Registered plan {run_id} in active_runs")

            return {
                "success": True,
                "plan": plan,
                "reasoning": f"Generated deterministic {planner_response.intent.value} plan with {len(planner_response.steps)} steps",
                "session_id": run_id,
            }

        except Exception as planner_error:
            logger.error(f"Planner error: {planner_error}")
            return {
                "success": False,
                "error": f"Planner validation failed: {str(planner_error)}",
                "plan": None,
                "session_id": None,
            }

    except Exception as e:
        logger.error(f"Plan generation error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "plan": None, "session_id": None}


# Phase 4.1.2: Next Step Execution Endpoint
class NextStepRequest(BaseModel):
    """Request body for next step execution"""

    run_id: str
    tool_result: Optional[Dict[str, Any]] = None


@router.post("/next")
async def execute_next_step(request: NextStepRequest) -> Dict[str, Any]:
    """
    Execute next step in plan or process tool result.
    Returns either ToolRequest or AssistantMessage.
    """
    try:
        run_id = request.run_id
        tool_result = request.tool_result

        if run_id not in active_runs:
            raise HTTPException(status_code=404, detail="Run not found")

        run_state = active_runs[run_id]

        # Process previous tool result if provided
        if tool_result:
            await process_tool_result(run_state, tool_result)

        # Find next step to execute
        next_step = find_next_step(run_state)

        if not next_step:
            # Plan completed
            run_state.status = "done"
            plan_goal = run_state.plan.goal if run_state.plan else ""
            goal_suffix = f" {plan_goal}" if plan_goal else ""
            return {
                "type": "assistant_message",
                "content": f"✅ Plan completed successfully!{goal_suffix}",
                "final": True,
            }

        # Execute step
        if next_step.tool:
            # Tool-based step - return tool request
            tool_request = create_tool_request(run_state, next_step)
            return {"type": "tool_request", "request": tool_request.dict()}
        else:
            # Reasoning step - return progress message
            next_step.status = "completed"
            run_state.current_step += 1
            return {
                "type": "assistant_message",
                "content": f"🔄 {next_step.title}",
                "final": False,
            }

    except Exception as e:
        logger.error(f"Next step execution error: {e}", exc_info=True)
        return {"type": "error", "error": str(e)}


# Phase 4.1.2: Plan Generation Helper Functions


async def generate_fix_diagnostics_plan(
    run_id: str, message: str, context: Dict[str, Any]
) -> Plan:
    """Generate plan for fixing diagnostics/problems"""
    diagnostics = context.get("diagnostics", [])

    steps = [
        PlanStep(
            id=f"{run_id}_1",
            title="Collect current diagnostics",
            tool="vscode.getDiagnostics",
            input={},
            verify=["diagnostics_collected"],
        ),
        PlanStep(
            id=f"{run_id}_2",
            title="Analyze error patterns",
            rationale="Group errors by type and severity for efficient fixing",
        ),
    ]

    # Add fix steps for each diagnostic
    for i, diag in enumerate(diagnostics[:3]):  # Limit to first 3 for now
        steps.append(
            PlanStep(
                id=f"{run_id}_{i+3}",
                title=f"Fix {diag.get('message', 'error')} in {diag.get('file', 'file')}",
                tool="workspace.readFile",
                input={"file": diag.get("file")},
                requires_approval=True,
                verify=["error_resolved"],
            )
        )

    steps.append(
        PlanStep(
            id=f"{run_id}_final",
            title="Verify all fixes applied",
            tool="vscode.getDiagnostics",
            input={},
            verify=["all_errors_resolved"],
        )
    )

    return Plan(
        id=run_id,
        goal="Fix all diagnostics in Problems tab",
        steps=steps,
        requires_approval=True,
        confidence=0.85,
        reasoning="Systematic approach to fix diagnostics by reading files, generating patches, and verifying results",
    )


async def generate_repo_inspection_plan(
    run_id: str, message: str, context: Dict[str, Any]
) -> Plan:
    """Generate plan for repository inspection"""
    steps = [
        PlanStep(
            id=f"{run_id}_1",
            title="Inspect workspace structure",
            rationale="Understanding project layout and key files",
        ),
        PlanStep(
            id=f"{run_id}_2",
            title="Identify project type and technology stack",
            rationale="Analyzing package files and configuration",
        ),
        PlanStep(
            id=f"{run_id}_3",
            title="Summarize repository purpose and architecture",
            rationale="High-level overview of what this codebase does",
        ),
    ]

    return Plan(
        id=run_id,
        goal="Provide comprehensive repository overview",
        steps=steps,
        requires_approval=False,
        confidence=0.9,
        reasoning="Repository inspection requires analyzing structure, technology stack, and purpose",
    )


async def generate_feature_implementation_plan(
    run_id: str, message: str, context: Dict[str, Any]
) -> Plan:
    """Generate plan for feature implementation"""
    steps = [
        PlanStep(
            id=f"{run_id}_1",
            title="Analyze feature requirements",
            rationale="Understanding what needs to be built",
        ),
        PlanStep(
            id=f"{run_id}_2",
            title="Design implementation approach",
            rationale="Planning architecture and file changes",
        ),
        PlanStep(
            id=f"{run_id}_3",
            title="Implement core functionality",
            requires_approval=True,
            tool="workspace.applyPatch",
            verify=["feature_implemented"],
        ),
        PlanStep(
            id=f"{run_id}_4",
            title="Add tests for new feature",
            requires_approval=True,
            tool="workspace.applyPatch",
            verify=["tests_added"],
        ),
        PlanStep(
            id=f"{run_id}_5",
            title="Verify implementation works",
            tool="tasks.run",
            input={"task": "test"},
            verify=["tests_pass"],
        ),
    ]

    return Plan(
        id=run_id,
        goal="Implement requested feature with tests",
        steps=steps,
        requires_approval=True,
        confidence=0.75,
        reasoning="Feature implementation requires analysis, coding, testing, and verification",
    )


async def generate_build_plan(
    run_id: str, message: str, context: Dict[str, Any]
) -> Plan:
    """Generate plan for build/run tasks"""
    steps = [
        PlanStep(
            id=f"{run_id}_1",
            title="Check project build configuration",
            rationale="Identifying available build scripts and tasks",
        ),
        PlanStep(
            id=f"{run_id}_2",
            title="Execute build process",
            tool="tasks.run",
            input={"task": "build"},
            verify=["build_success"],
        ),
        PlanStep(
            id=f"{run_id}_3",
            title="Report build results",
            rationale="Summary of build outcome and any issues",
        ),
    ]

    return Plan(
        id=run_id,
        goal="Build and run the project",
        steps=steps,
        requires_approval=False,
        confidence=0.8,
        reasoning="Build process involves checking configuration and executing build tasks",
    )


async def generate_test_plan(
    run_id: str, message: str, context: Dict[str, Any]
) -> Plan:
    """Generate plan for running tests"""
    steps = [
        PlanStep(
            id=f"{run_id}_1",
            title="Identify test configuration",
            rationale="Finding test scripts and setup",
        ),
        PlanStep(
            id=f"{run_id}_2",
            title="Execute test suite",
            tool="tasks.run",
            input={"task": "test"},
            verify=["tests_completed"],
        ),
        PlanStep(
            id=f"{run_id}_3",
            title="Analyze test results",
            rationale="Report on test outcomes and any failures",
        ),
    ]

    return Plan(
        id=run_id,
        goal="Run project tests and report results",
        steps=steps,
        requires_approval=False,
        confidence=0.85,
        reasoning="Test execution involves configuration check, running tests, and reporting results",
    )


async def generate_explanation_plan(
    run_id: str, message: str, context: Dict[str, Any]
) -> Plan:
    """Generate plan for general explanations"""
    steps = [
        PlanStep(
            id=f"{run_id}_1",
            title="Analyze user question",
            rationale="Understanding what information is being requested",
        ),
        PlanStep(
            id=f"{run_id}_2",
            title="Provide comprehensive explanation",
            rationale="Detailed response based on available context",
        ),
    ]

    return Plan(
        id=run_id,
        goal="Provide helpful explanation",
        steps=steps,
        requires_approval=False,
        confidence=0.7,
        reasoning="General explanation based on user question and context",
    )


# Helper functions for step execution
def find_next_step(run_state: RunState) -> Optional[PlanStep]:
    """Find next pending step in plan"""
    if not run_state.plan:
        return None

    for step in run_state.plan.steps:
        if step.status == "pending":
            step.status = "active"
            return step
    return None


def create_tool_request(run_state: RunState, step: PlanStep) -> ToolRequest:
    """Create tool request for step execution"""
    request_id = f"{step.id}_req_{int(time.time())}"
    if not step.tool:
        raise ValueError(f"Tool name is required for step {step.id}")
    tool_name = step.tool

    approval = {
        "required": step.requires_approval,
        "reason": step.rationale or f"Execute {step.title}",
        "risk": "high" if step.requires_approval else "low",
    }

    # Phase 4.1 Step 3: Include previous tool result for chaining
    args = step.input or {}
    if run_state.artifacts:
        # Get the most recent tool result as previousResult
        latest_artifact = run_state.artifacts[-1]
        args["previousResult"] = latest_artifact["result"]

    return ToolRequest(
        run_id=run_state.run_id,
        request_id=request_id,
        tool=tool_name,
        args=args,
        approval=approval,
    )


async def process_tool_result(run_state: RunState, tool_result: Dict[str, Any]):
    """Process result from tool execution"""
    if not run_state.plan:
        return
    # Find the corresponding step and update status
    for step in run_state.plan.steps:
        if step.status == "active":
            if tool_result.get("ok", False):
                step.status = "completed"
                run_state.current_step += 1
                # Store result as artifact
                run_state.artifacts.append(
                    {
                        "step_id": step.id,
                        "tool": tool_result.get("tool"),
                        "result": tool_result.get("output"),
                    }
                )
            else:
                step.status = "failed"
                run_state.status = "failed"
            break


@router.post("/analyze-changes")
async def analyze_working_changes(
    request: Request,
    workspace_root: Optional[str] = None,
) -> StreamingResponse:
    """
    Analyze working tree changes with real-time progress updates.
    Returns Server-Sent Events (SSE) for live progress streaming.
    """

    async def generate_analysis_stream():
        import asyncio
        import json
        from concurrent.futures import ThreadPoolExecutor

        try:
            # Send immediate response to show we're alive
            yield f"data: {json.dumps({'type': 'progress', 'step': '🔄 Starting analysis...', 'progress': 0})}\n\n"

            # Get workspace root from query parameter or request body
            actual_workspace_root = workspace_root
            if not actual_workspace_root:
                try:
                    body = await request.json()
                    actual_workspace_root = body.get("workspace_root")
                except Exception as e:
                    logger.warning(f"Could not parse request body: {e}")
            actual_workspace_root = actual_workspace_root or os.getcwd()

            yield f"data: {json.dumps({'type': 'progress', 'step': f'📁 Workspace: {actual_workspace_root}', 'progress': 5})}\n\n"

            # Use thread pool to run blocking service initialization without blocking event loop
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)

            def init_service_sync():
                """Initialize service in thread pool"""
                try:
                    from backend.services.review_service import RealReviewService

                    return RealReviewService(
                        repo_path=actual_workspace_root, analysis_depth="comprehensive"
                    )
                except Exception as e:
                    logger.warning(f"Could not initialize RealReviewService: {e}")
                    return None

            yield f"data: {json.dumps({'type': 'progress', 'step': 'Initializing analysis service...', 'progress': 10})}\n\n"

            try:
                service = await asyncio.wait_for(
                    loop.run_in_executor(executor, init_service_sync), timeout=5.0
                )
                if service:
                    yield f"data: {json.dumps({'type': 'progress', 'step': '✅ Analysis service ready', 'progress': 15})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'progress', 'step': '⚠️ Using basic analysis mode', 'progress': 15})}\n\n"
                    service = None
            except asyncio.TimeoutError:
                logger.warning("Service initialization timeout, using basic analysis")
                yield f"data: {json.dumps({'type': 'progress', 'step': '⚠️ Service init timeout, using basic mode', 'progress': 15})}\n\n"
                service = None

            # Get working tree changes
            yield f"data: {json.dumps({'type': 'progress', 'step': 'Scanning for changes...', 'progress': 20})}\n\n"

            def get_changes_sync():
                """Get changes in thread pool"""
                try:
                    repo_service = (
                        getattr(service, "repo_service", None) if service else None
                    )
                    if repo_service is None:
                        from backend.services.repo_service import RepoService

                        repo_service = RepoService(actual_workspace_root)

                    has_head = repo_service.git.has_head()
                    changes = repo_service.get_working_tree_changes()
                    skip_summary = getattr(repo_service, "last_skip_summary", {}) or {}
                    return changes, has_head, None, skip_summary
                except Exception as e:
                    logger.warning(f"Could not get changes: {e}")
                    return [], None, str(e), {}

            try:
                changes, has_head, repo_error, skip_summary = await asyncio.wait_for(
                    loop.run_in_executor(executor, get_changes_sync), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.error("Getting changes timed out")
                changes, has_head, repo_error, skip_summary = (
                    [],
                    None,
                    "Timed out while scanning for changes.",
                    {},
                )
            except Exception as e:
                logger.error(f"Error getting changes: {e}")
                changes, has_head, repo_error, skip_summary = [], None, str(e), {}

            head_warning = None
            if repo_error:
                head_warning = (
                    "This folder does not look like a Git repository. "
                    "Open the repo root (the folder containing `.git`) or run `git init`."
                )
            elif has_head is False:
                head_warning = (
                    "This repo has no commits yet, so I cannot diff against main/HEAD. "
                    'Create an initial commit (`git add -A` then `git commit -m "Initial commit"`), '
                    "or fetch and check out `main` if you expect a remote branch."
                )
                yield f"data: {json.dumps({'type': 'progress', 'step': head_warning, 'progress': 22})}\n\n"

            skip_warning = None
            if skip_summary.get("skipped_total"):
                parts = []
                if skip_summary.get("skipped_large"):
                    max_bytes = skip_summary.get("max_file_bytes")
                    size_hint = f" (> {max_bytes} bytes)" if max_bytes else ""
                    parts.append(
                        f"Skipped {skip_summary.get('skipped_large')} large files{size_hint}"
                    )
                if skip_summary.get("skipped_ignored"):
                    parts.append(
                        f"Skipped {skip_summary.get('skipped_ignored')} ignored/binary files"
                    )
                skip_warning = " · ".join(parts) if parts else None

            if not changes:
                warning = " ".join([w for w in [head_warning, skip_warning] if w])
                yield f"data: {json.dumps({'type': 'progress', 'step': 'No changes found or unable to scan', 'progress': 100})}\n\n"
                yield f"data: {json.dumps({'type': 'complete', 'results': [], 'warning': warning})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'progress', 'step': f'Found {len(changes)} changed files', 'progress': 30})}\n\n"

            # Analyze each file
            review_files = []
            for i, change in enumerate(
                changes[:50]
            ):  # Limit to prevent overwhelming response
                progress = 30 + (i * 60 // min(len(changes), 50))
                file_path = change.get("path", f"file_{i}")

                yield f"data: {json.dumps({'type': 'progress', 'step': f'Analyzing {file_path}...', 'progress': progress})}\n\n"

                try:
                    if service:
                        # Run comprehensive analysis in thread pool
                        def analyze_file_sync():
                            try:
                                return service.analyze_file_change_comprehensive(change)
                            except Exception as e:
                                logger.warning(f"Error in comprehensive analysis: {e}")
                                return {}

                        result = await asyncio.wait_for(
                            loop.run_in_executor(executor, analyze_file_sync),
                            timeout=15.0,
                        )
                    else:
                        result = {}

                    # Extract issues from result
                    issues = []
                    if isinstance(result, dict):
                        analysis_results = result.get("analysis_results", {})
                        if isinstance(analysis_results, dict):
                            for analysis_type, analysis_obj in analysis_results.items():
                                if hasattr(analysis_obj, "issues"):
                                    for issue in analysis_obj.issues:
                                        issues.append(
                                            {
                                                "id": f"issue-{i}-{len(issues)}",
                                                "title": getattr(
                                                    issue, "title", "Issue"
                                                ),
                                                "body": getattr(
                                                    issue, "message", str(issue)
                                                ),
                                                "severity": getattr(
                                                    issue, "severity", "medium"
                                                ),
                                                "canAutoFix": bool(
                                                    getattr(issue, "suggestion", None)
                                                ),
                                            }
                                        )

                    review_files.append(
                        {
                            "path": file_path,
                            "severity": (
                                "high"
                                if any(i["severity"] == "high" for i in issues)
                                else "medium" if issues else "low"
                            ),
                            "issues": issues,
                            "diff": change.get("diff", "")[:1000],
                        }
                    )

                except asyncio.TimeoutError:
                    logger.error(f"Analysis timeout for {file_path}")
                    review_files.append(
                        {
                            "path": file_path,
                            "severity": "low",
                            "issues": [],
                            "diff": change.get("diff", "")[:500],
                        }
                    )
                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {e}")
                    review_files.append(
                        {
                            "path": file_path,
                            "severity": "low",
                            "issues": [],
                            "diff": change.get("diff", "")[:500],
                        }
                    )

            yield f"data: {json.dumps({'type': 'progress', 'step': 'Analysis complete', 'progress': 95})}\n\n"
            warning = " ".join([w for w in [head_warning, skip_warning] if w])
            yield f"data: {json.dumps({'type': 'complete', 'results': review_files, 'progress': 100, 'warning': warning})}\n\n"

        except Exception as e:
            import traceback

            error_msg = f"Error in analysis: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"

    return StreamingResponse(
        generate_analysis_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/repo/review/stream")
async def stream_repo_review(
    workspace_root: Optional[str] = None,
    max_files: Optional[int] = None,
) -> StreamingResponse:
    """
    SSE endpoint to stream structured review with real file content.
    Follows the specification for live review streaming.
    """

    async def generate_review_stream():
        from backend.services.review_service import (
            generate_review_stream as ai_review_stream,
        )

        try:
            actual_workspace_root = workspace_root or os.getcwd()

            # Initial progress
            yield f"data: {json.dumps({'kind': 'liveProgress', 'step': '🔍 Starting AI analysis...', 'workspace': actual_workspace_root})}\n\n"

            all_review_entries = []
            total_files = 0

            # Stream AI-powered analysis
            async for event in ai_review_stream(actual_workspace_root):
                event_type = event.get("type")
                event_data = event.get("data") or {}
                if not isinstance(event_data, dict):
                    event_data = {}

                if event_type == "live-progress":
                    # Convert to extension format
                    yield f"data: {json.dumps({'kind': 'liveProgress', 'step': event_data})}\n\n"

                elif event_type == "review-entry":
                    # Convert AI review entry to extension format
                    total_files += 1
                    entry = {
                        "id": f"ai-entry-{total_files}",
                        "filePath": event_data.get("file", "unknown"),
                        "diff": event_data.get("hunk", ""),
                        "issues": [
                            {
                                "id": event_data.get("fixId", f"issue-{total_files}"),
                                "title": event_data.get("title", "Code issue"),
                                "description": event_data.get("body", ""),
                                "severity": event_data.get("severity", "info"),
                                "canAutoFix": True,
                            }
                        ],
                        "severity": event_data.get("severity", "info"),
                    }
                    all_review_entries.append(entry)

                    # Stream each entry to frontend
                    yield f"data: {json.dumps({'kind': 'reviewEntry', 'entry': entry, 'processed': total_files, 'total': total_files})}\n\n"

                elif event_type == "done":
                    # Send final summary
                    summary_payload = {
                        "kind": "reviewSummary",
                        "totalFiles": total_files,
                        "listedFiles": [
                            e.get("filePath", "unknown")
                            for e in all_review_entries[:50]
                        ],
                        "skippedFiles": 0,
                        "message": f"AI analysis complete - {total_files} files reviewed",
                    }
                    yield f"data: {json.dumps(summary_payload)}\n\n"
                    yield f"data: {json.dumps({'kind': 'liveProgress', 'step': f'✅ Review complete - {total_files} files analyzed!'})}\n\n"
                    yield f"data: {json.dumps({'kind': 'done', 'summary': summary_payload})}\n\n"
                    return

                elif event_type == "error":
                    yield f"data: {json.dumps({'kind': 'error', 'message': event_data.get('message', 'Analysis error')})}\n\n"
                    return

            # Fallback if no done event
            if total_files == 0:
                summary_payload = {
                    "kind": "reviewSummary",
                    "totalFiles": 0,
                    "listedFiles": [],
                    "skippedFiles": 0,
                    "message": "No changes detected",
                }
                yield f"data: {json.dumps(summary_payload)}\n\n"
                yield f"data: {json.dumps({'kind': 'done', 'summary': summary_payload})}\n\n"

        except Exception as e:
            logger.error(f"Error in AI review stream: {e}")
            import traceback

            traceback.print_exc()
            yield f"data: {json.dumps({'kind': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_review_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/test-auto-fix")
async def test_auto_fix():
    """Test endpoint to verify router is working."""
    return {"status": "auto-fix router is working"}


@router.get("/test-stream")
async def test_stream():
    """Simple test streaming endpoint."""

    async def generate_test_stream():
        import asyncio

        for i in range(5):
            yield f"data: {json.dumps({'type': 'progress', 'step': f'Test message {i+1}', 'progress': (i+1) * 20})}\n\n"
            await asyncio.sleep(0.5)  # Small delay
        yield f"data: {json.dumps({'type': 'complete', 'step': 'Test completed', 'progress': 100})}\n\n"

    return StreamingResponse(
        generate_test_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/auto-fix")
async def auto_fix_issues(
    request: Request,
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Legacy auto-fix endpoint for bulk operations."""
    return await _apply_auto_fix(request, workspace_root)


@router.post("/repo/fix/{fix_id}")
async def auto_fix_by_id(
    fix_id: str,
    request: Request,
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply a single auto-fix by fix ID."""
    try:
        body = await request.json() if hasattr(request, "json") else {}
        file_path = body.get("path") or body.get("filePath")

        if not file_path:
            return {"success": False, "error": "Missing file path"}

        # Use the existing auto-fix logic with a single fix
        # Create a mock request object
        class MockRequest:
            def __init__(self, body_data):
                self._body = body_data

            async def json(self):
                return self._body

        # mock_request = MockRequest(mock_request_body)
        # return await _apply_auto_fix(mock_request, workspace_root)  # Fix type mismatch
        return {"success": False, "error": "Auto-fix not implemented"}

    except Exception as e:
        logger.error(f"Error in auto-fix by ID {fix_id}: {e}")
        return {"success": False, "error": str(e)}


@router.post("/consent/{consent_id}")
async def handle_consent_response(
    consent_id: str,
    request: Request,
) -> Dict[str, Any]:
    """
    Handle user consent approval/denial for dangerous commands.

    The frontend sends consent responses when the user approves or denies
    a dangerous command execution (e.g., rm, kill, chmod).
    """
    try:
        # Import the global consent storage from autonomous_agent
        from backend.services.autonomous_agent import _consent_approvals

        body = await request.json()
        approved = body.get("approved", False)
        command = body.get("command", "")

        logger.info(f"[NAVI API] 🔐 Consent {consent_id}: {'APPROVED' if approved else 'DENIED'} for command: {command}")

        # Update the consent approval in global storage
        if consent_id in _consent_approvals:
            _consent_approvals[consent_id]["approved"] = approved
            _consent_approvals[consent_id]["pending"] = False
            _consent_approvals[consent_id]["response_timestamp"] = time.time()
        else:
            # Consent ID not found (might have expired or already processed)
            logger.warning(f"[NAVI API] Consent {consent_id} not found in pending approvals")
            _consent_approvals[consent_id] = {
                "approved": approved,
                "command": command,
                "timestamp": time.time(),
                "pending": False,
                "response_timestamp": time.time()
            }

        return {
            "success": True,
            "consent_id": consent_id,
            "approved": approved,
            "message": f"Consent {'approved' if approved else 'denied'}"
        }

    except Exception as e:
        logger.error(f"[NAVI API] Error handling consent {consent_id}: {e}")
        return {"success": False, "error": str(e)}


async def _apply_auto_fix(
    request: Request, workspace_root: Optional[str] = None
) -> Dict[str, Any]:
    """
    Apply automated fixes to files based on fixId.
    """
    try:
        body = await request.json()
        file_path = body.get("path") or body.get("filePath")
        fix_ids = body.get("fixes", [])

        if not file_path or not fix_ids:
            return {"success": False, "error": "Missing path or fixes"}

        # Get workspace root
        actual_workspace = workspace_root or body.get("workspace_root") or os.getcwd()

        full_path = os.path.join(actual_workspace, file_path)

        if not os.path.exists(full_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        # Read current file content
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        applied_fixes = []

        # Apply fixes based on fixId using built-in implementation
        for fix_id in fix_ids:
            modified_content, success, description = await _apply_auto_fix_by_id(
                content, fix_id, file_path, {"workspace_root": workspace_root}
            )

            if success:
                content = modified_content
                applied_fixes.append(
                    {"fix_id": fix_id, "description": description, "success": True}
                )
            else:
                applied_fixes.append(
                    {"fix_id": fix_id, "description": description, "success": False}
                )

        # Check if any fixes were successfully applied
        successful_fixes = [fix for fix in applied_fixes if fix.get("success", False)]

        # Write back the modified content if any fixes were applied
        if successful_fixes:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {
                "success": True,
                "applied_fixes": successful_fixes,
                "failed_fixes": [
                    fix for fix in applied_fixes if not fix.get("success", False)
                ],
                "file_path": file_path,
                "changes_made": True,
                "total_fixes": len(successful_fixes),
            }
        else:
            return {
                "success": True,
                "applied_fixes": [],
                "failed_fixes": applied_fixes,
                "file_path": file_path,
                "changes_made": False,
                "message": "No fixes could be applied successfully",
            }

    except Exception as e:
        logger.error(f"Error in auto-fix: {e}")
        return {"success": False, "error": str(e)}


def _looks_like_jira_my_issues(message: str) -> bool:
    """Check if message is asking for user's Jira issues."""
    msg = message.lower()
    has_jira = any(k in msg for k in JIRA_KEYWORDS)
    has_me = (
        any(k in msg for k in ME_KEYWORDS) or "assigned to me" in msg or "my " in msg
    )
    return has_jira and has_me


def _is_smalltalk(message: str) -> bool:
    """Lightweight detector for non-work chatter."""
    msg = (message or "").lower().strip()
    if not msg:
        return False
    smalltalk_phrases = (
        "how are you",
        "what's up",
        "what is up",
        "how are you doing",
        "hello",
        "hi",
        "hey",
        "latest news",
        "news",
        "what's going on",
        "what is going on",
    )
    if any(p in msg for p in smalltalk_phrases):
        return True
    # If very short and contains no work keywords, treat as small talk
    if len(msg) <= 40 and not any(k in msg for k in WORK_KEYWORDS):
        return True
    return False


def _get_repo_name_from_path(path_str: Optional[str]) -> Optional[str]:
    """Derive repo name from a filesystem path (workspace root or file path)."""
    if not path_str:
        return None
    try:
        return Path(path_str).name or None
    except Exception:
        return None


_REPO_WHERE_PHRASES = (
    "which repo are we in",
    "which repository are we in",
    "which repo am i in",
    "which repository am i in",
    "what repo are we in",
    "what repository are we in",
    "which project are we in",
    "what project are we in",
    "where are we",
    "what workspace are we in",
    "which workspace are we in",
)


def _looks_like_repo_where(message: str) -> bool:
    msg = (message or "").lower()
    return any(p in msg for p in _REPO_WHERE_PHRASES)


def _looks_like_repo_explain(message: str) -> bool:
    """
    Detects 'explain this repo/project' style questions so we can take
    the fast-path that scans the workspace.
    """
    msg = (message or "").lower()
    patterns = (
        "explain this repo",
        "explain this project",
        "explain about this repo",
        "explain about this project",
        "what does this repo do",
        "what does this project do",
        "summarize this repo",
        "summarize this project",
        "explain the current repo",
        "explain the current project",
        "can you explain this repo",
        "can you explain this project",
        "describe this repo",
        "describe this project",
    )
    return any(p in msg for p in patterns)


def _looks_like_generate_tests(message: str) -> bool:
    msg = (message or "").lower()
    patterns = (
        "generate tests for this file",
        "generate unit tests for this file",
        "write tests for this file",
        "create tests for this file",
        "generate jest tests",
        "generate vitest tests",
        "generate unit tests",
    )
    return any(p in msg for p in patterns)


def _looks_like_coverage_request(message: str) -> bool:
    msg = (message or "").lower()
    patterns = (
        "coverage",
        "test coverage",
        "coverage threshold",
        "coverage %",
        "coverage percent",
        "ensure coverage",
        "increase coverage",
        "code coverage",
    )
    return any(p in msg for p in patterns)


def _extract_coverage_target(message: str) -> Optional[int]:
    if not message:
        return None
    match = re.search(r"(\d{1,3})\s*%+", message)
    if not match:
        return None
    value = int(match.group(1))
    if value <= 0 or value > 100:
        return None
    return value


def _pick_node_runner(pkg: Dict[str, Any], root: Path) -> str:
    pm = str(pkg.get("packageManager") or "").lower()
    if pm.startswith("yarn"):
        return "yarn"
    if pm.startswith("pnpm"):
        return "pnpm"
    if pm.startswith("npm"):
        return "npm"
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _detect_coverage_commands(workspace_root: str) -> List[str]:
    root = Path(workspace_root)
    cmds: List[str] = []

    pkg_path = root / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pkg = {}

        scripts = pkg.get("scripts") or {}
        runner = _pick_node_runner(pkg, root)

        if "coverage" in scripts:
            if runner == "yarn":
                cmds.append("yarn coverage")
            elif runner == "pnpm":
                cmds.append("pnpm run coverage")
            else:
                cmds.append("npm run coverage")
        elif "test" in scripts:
            if runner == "yarn":
                cmds.append("yarn test --coverage")
            elif runner == "pnpm":
                cmds.append("pnpm test -- --coverage")
            else:
                cmds.append("npm test -- --coverage")

    has_pytest = (root / "pytest.ini").exists() or (root / "pyproject.toml").exists()
    if has_pytest:
        cmds.append("pytest --cov=. --cov-report=term-missing")

    if (root / "go.mod").exists():
        cmds.append("go test ./... -cover")

    return cmds


def _get_coverage_threshold(
    *,
    message: str,
    db: Session,
    org_id: Optional[str],
) -> int:
    explicit = _extract_coverage_target(message)
    if explicit is not None:
        return explicit

    default_value = int(os.getenv("NAVI_TEST_COVERAGE_MIN", "80"))
    if not org_id:
        return default_value

    try:
        row = (
            db.execute(
                text("SELECT test_coverage_min FROM org_policy WHERE org_id=:o"),
                {"o": org_id},
            )
            .mappings()
            .first()
        )
    except Exception:
        row = None

    if row and row.get("test_coverage_min") is not None:
        try:
            return int(row["test_coverage_min"])
        except Exception:
            return default_value

    return default_value


def _looks_like_code_edit(message: str) -> bool:
    """
    Detect 'please fix/refactor/implement' type requests
    where the user is likely expecting direct code changes.
    """
    msg = (message or "").lower()
    patterns = (
        "fix this code",
        "fix the code",
        "fix compilation error",
        "fix build error",
        "fix type error",
        "fix the typescript errors",
        "refactor this",
        "refactor this code",
        "improve this code",
        "optimize this function",
        "rewrite this function",
        "implement this function",
        "add tests for this",
        "write tests for this",
        "generate test cases for this file",
        "generate testcases for this file",
    )
    return any(p in msg for p in patterns)


def _looks_like_repo_scan(message: str) -> bool:
    """Heuristic for 'scan this repo and list folders/entrypoints' questions."""
    msg = (message or "").lower()
    patterns = (
        "scan this repo",
        "scan the repo",
        "scan repo",
        "scan this project",
        "scan the project",
        "list the main folders",
        "list main folders",
        "show the main folders",
        "show me the main folders",
        "list key folders",
        "list key directories",
        "list the key directories",
        "show me the important configuration and extension files",
        "show important configuration files",
        "list the entrypoints",
        "list main entrypoints",
        "what are the main entrypoints",
        "where are the entrypoints",
    )
    return any(p in msg for p in patterns)


def _looks_like_check_errors(message: str) -> bool:
    """
    Detects messages like 'check errors & fix them', 'check errors', 'run tests and fix',
    etc. This is used for the 'Check errors & fix' quick action.
    """
    msg = (message or "").lower()
    patterns = (
        "check errors & fix",
        "check errors and fix",
        "check errors and fix them",
        "check errors",
        "fix errors",
        "run tests and fix",
        "run tests & fix",
        "run tests",
        "run the tests",
        "run lint",
        "run lints",
        "check build",
        "check for errors",
    )
    return any(p in msg for p in patterns)


def _looks_like_git_head_check(message: str) -> bool:
    """
    Detect questions about whether the repo has a valid HEAD / commits.
    """
    msg = (message or "").lower()
    patterns = (
        "valid head",
        "git head",
        "head commit",
        "no head",
        "no commits",
        "no commit",
        "initial commit",
        "is there a head",
        "has head",
        "check head",
        "head exists",
    )
    return any(p in msg for p in patterns)


def _looks_like_git_review_request(message: str) -> bool:
    """
    Detect requests that imply git diff/review against main/HEAD.
    """
    msg = (message or "").lower()
    keywords = (
        "review",
        "diff",
        "changes",
        "compare",
        "git",
        "main",
        "master",
        "branch",
        "analyze",
    )
    return any(k in msg for k in keywords)


def _extract_git_command(message: str) -> Optional[str]:
    """
    Best-effort extraction of a git command from user text.
    Returns the raw git command string (e.g. "git status") or None.
    """
    if not message:
        return None

    text = message.strip()
    if not text:
        return None

    code_match = re.search(r"`(git[^`]+)`", text)
    if code_match:
        cmd = code_match.group(1)
        return cmd.strip().rstrip("?.!;")

    lowered = text.lower()
    if lowered.startswith("git "):
        return text.rstrip("?.!;")

    run_match = re.search(
        r"\b(?:run|execute|do|please run|can you run)\s+(git\s+[^\n]+)",
        text,
        re.IGNORECASE,
    )
    if run_match:
        cmd = run_match.group(1)
        return cmd.strip().rstrip("?.!;")

    return None


def _infer_git_command_from_text(message: str) -> Optional[Dict[str, Any]]:
    """
    Map common natural-language git requests to a concrete git command.
    Only returns safe, read-only commands.
    """
    if not message:
        return None

    msg = message.lower()
    if not msg.strip():
        return None

    # Avoid hijacking review-style intents; let repo review handle those.
    if re.search(r"\b(review|analyz|analyse|audit|inspect|quality)\b", msg):
        return None

    git_related = any(
        token in msg
        for token in (
            "git",
            "branch",
            "commit",
            "diff",
            "history",
            "log",
            "remote",
        )
    )
    if not git_related:
        return None

    def has(*phrases: str) -> bool:
        return any(p in msg for p in phrases)

    if has("status", "working tree", "staged", "unstaged"):
        return {
            "command": "git status -sb",
            "description": "Show git status",
            "requires_head": False,
        }

    if re.search(r"\b(current|active|which|what)\s+branch\b", msg):
        return {
            "command": "git rev-parse --abbrev-ref HEAD",
            "description": "Show current branch",
            "requires_head": False,
        }

    if "branch" in msg or "branches" in msg:
        return {
            "command": "git branch -vv",
            "description": "List branches",
            "requires_head": False,
        }

    if has("last commit", "latest commit"):
        return {
            "command": "git log -1 --stat",
            "description": "Show latest commit",
            "requires_head": True,
        }

    if has("log", "history", "recent commits", "commit history"):
        return {
            "command": "git log --oneline -n 10",
            "description": "Show recent commits",
            "requires_head": True,
        }

    if "remote" in msg or "remotes" in msg:
        return {
            "command": "git remote -v",
            "description": "List remotes",
            "requires_head": False,
        }

    diff_intent = (
        "diff" in msg
        or "compare" in msg
        or ("changes" in msg and re.search(r"\b(git|branch|main|master)\b", msg))
    )
    if diff_intent:
        if has("staged", "cached"):
            return {
                "command": "git diff --cached --stat",
                "description": "Show staged changes",
                "requires_head": True,
            }
        if re.search(r"\b(files|file list|name-only|names)\b", msg):
            return {
                "command": "git diff --name-only",
                "description": "List changed files",
                "requires_head": True,
            }
        if "main" in msg:
            return {
                "command": "git diff --stat main...HEAD",
                "description": "Compare changes against main",
                "requires_head": True,
            }
        if "master" in msg:
            return {
                "command": "git diff --stat master...HEAD",
                "description": "Compare changes against master",
                "requires_head": True,
            }
        return {
            "command": "git diff --stat",
            "description": "Show changes",
            "requires_head": True,
        }

    return None


def _is_safe_git_command(command: str) -> Tuple[bool, str]:
    """
    Validate a git command string for basic safety and shape.
    """
    cmd = (command or "").strip()
    if not cmd.startswith("git "):
        return False, "Command must start with `git`."

    bad_tokens = [";", "&&", "||", "|", ">", "<", "`", "$(", "\n", "\r"]
    if any(tok in cmd for tok in bad_tokens):
        return False, "Command contains shell control characters."

    if len(cmd) > 400:
        return False, "Command is too long."

    if not re.match(r"^[A-Za-z0-9_\-./:=+ \t'\"@]+$", cmd):
        return False, "Command contains unsupported characters."

    return True, ""


def _edits_to_actions(edits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert LLM edits to extension-ready editFile actions.
    """
    actions: List[Dict[str, Any]] = []
    for edit in edits:
        path = edit.get("path")
        new_content = edit.get("newContent")
        if not path or not isinstance(path, str) or not isinstance(new_content, str):
            continue
        actions.append(
            {
                "type": "editFile",
                "filePath": path,
                "content": new_content,
                "description": (edit.get("description") or "").strip() or None,
            }
        )
    return actions


# ============================================================================
# SHARED HELPER FUNCTIONS FOR DIAGNOSTICS AND CODE EDITING
# ============================================================================


async def _run_command(
    cmd: List[str],
    cwd: str,
    timeout: int = 240,
) -> Dict[str, Any]:
    """
    Run a single command in the workspace and capture exit code + combined output.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        # e.g. npm not installed
        return {
            "cmd": cmd,
            "exit_code": -127,
            "output": f"Failed to execute {' '.join(cmd)}: command not found.",
        }

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return {
            "cmd": cmd,
            "exit_code": -1,
            "output": f"Command {' '.join(cmd)} timed out after {timeout}s.",
        }

    text_out = ""
    if stdout:
        text_out += stdout.decode("utf-8", errors="ignore")
    if stderr:
        if text_out:
            text_out += "\n\n"
        text_out += stderr.decode("utf-8", errors="ignore")

    return {"cmd": cmd, "exit_code": proc.returncode, "output": text_out}


def _detect_js_diagnostic_commands(workspace_root: str) -> List[List[str]]:
    """
    Very simple heuristic: if package.json exists, run npm/yarn/pnpm test & lint if present.
    You can extend this later (pytest, mvn test, etc.).
    """
    root = Path(workspace_root)
    pkg_path = root / "package.json"
    if not pkg_path.exists():
        return []

    try:
        with pkg_path.open("r", encoding="utf-8") as f:
            pkg = json.load(f)
    except Exception:  # noqa: BLE001
        return []

    scripts = pkg.get("scripts") or {}
    cmds: List[List[str]] = []

    runner = _pick_node_runner(pkg, root)

    def add_script(script: str, extra: Optional[List[str]] = None) -> None:
        if script not in scripts:
            return
        suffix = extra or []
        if runner == "yarn":
            cmds.append(["yarn", script, *suffix])
        elif runner == "pnpm":
            cmds.append(["pnpm", "run", script, *suffix])
        else:
            cmds.append(["npm", "run", script, *suffix])

    if "lint" in scripts:
        add_script("lint", ["--", "--max-warnings=0"])
    if "typecheck" in scripts:
        add_script("typecheck")
    if "test" in scripts:
        add_script("test", ["--", "--watch=false", "--runInBand"])
    if not cmds and "build" in scripts:
        add_script("build")

    return cmds


def _detect_repo_diagnostic_commands(workspace_root: str) -> List[List[str]]:
    """
    Detect diagnostics commands across common stacks (Node, Python, Go).
    """
    root = Path(workspace_root)
    cmds: List[List[str]] = []

    cmds.extend(_detect_js_diagnostic_commands(workspace_root))

    has_pytest = (
        (root / "pytest.ini").exists()
        or (root / "pyproject.toml").exists()
        or (root / "setup.cfg").exists()
    )
    has_py_tests = bool(
        list(root.glob("tests/**/*.py")) or list(root.glob("test_*.py"))
    )
    if has_pytest or has_py_tests:
        cmds.append(["pytest", "-q"])

    if (root / "go.mod").exists():
        cmds.append(["go", "test", "./..."])

    return cmds[:2]


async def _collect_repo_diagnostics(workspace_root: str) -> Dict[str, Any]:
    """
    Run one or more diagnostic commands (lint/tests) and return combined output.
    """
    cmds = _detect_repo_diagnostic_commands(workspace_root)
    if not cmds:
        return {"commands": [], "raw": ""}

    results = []
    for cmd in cmds:
        res = await _run_command(cmd, cwd=workspace_root)
        results.append(res)

    combined = []
    for r in results:
        cmd_str = " ".join(r["cmd"])
        combined.append(f"$ {cmd_str}\n(exit {r['exit_code']})\n{r['output']}")
    raw = "\n\n".join(combined)

    return {"commands": results, "raw": raw}


def _extract_error_files_from_diagnostics(
    raw_output: str,
    workspace_root: str,
) -> List[str]:
    """
    Heuristically pull file paths from diagnostics (TS/JS/etc).
    Returns paths relative to workspace_root.
    """
    if not raw_output or not workspace_root:
        return []

    root = Path(workspace_root)
    candidates: set[str] = set()

    # Pattern: some/path/File.tsx:123:45
    pattern = r"([^\s:]+?\.(?:ts|tsx|js|jsx|mjs|cjs|py|java|cs|go|rb|php)):(\d+):(\d+)"
    for match in re.finditer(pattern, raw_output):
        rel_or_abs = match.group(1)
        path = Path(rel_or_abs)
        if not path.is_absolute():
            path = root / path

        if path.is_file():
            try:
                rel = str(path.relative_to(root))
            except Exception:  # noqa: BLE001
                rel = str(path)
            candidates.add(rel)

    # You can add more patterns over time (e.g. Jest stack traces).

    return sorted(candidates)


async def _generate_edits_with_llm(
    *,
    model_name: str,
    workspace_root: Optional[str],
    task_message: str,
    files: List[Dict[str, Any]],
    diagnostics: Optional[str] = None,
    mode: str = "generic",  # "generic" | "diagnostics" | "tests"
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Shared LLM call that returns (summary, normalized_edits).
    """
    if not OPENAI_ENABLED or openai_client is None:
        raise RuntimeError("OpenAI is not enabled")

    base_prompt = (
        "You are Navi, an AI pair programmer integrated into VS Code.\n"
        "Your job is to propose concrete code edits for the attached files.\n\n"
        "You MUST respond with a single JSON object of the form:\n"
        "{\n"
        '  "summary": string,           // high-level explanation for the user\n'
        '  "edits": [                  // list of edits to apply\n'
        "    {\n"
        '      "path": string,         // file path, as provided in the input\n'
        '      "newContent": string,   // full new file content AFTER edits\n'
        '      "description"?: string  // optional: what this edit does\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Prefer whole-file replacements (`newContent` is the entire updated file), "
        "not tiny fragments.\n"
        "- Preserve unrelated code and comments.\n"
        "- Do NOT invent random new files unless you are clearly asked to (for tests).\n"
        "- Ensure the code compiles or runs according to the language conventions.\n"
        "- Do NOT include any markdown or explanation outside of the JSON object.\n"
    )

    if mode == "diagnostics":
        base_prompt += (
            "\nAdditional instructions:\n"
            "- Use the diagnostics output to identify the root causes of failures.\n"
            "- Prioritize edits that make failing commands pass (lint, tests, typechecks).\n"
            "- Avoid cosmetic refactors unless they directly help fix the errors.\n"
        )
    elif mode == "tests":
        base_prompt += (
            "\nAdditional instructions for TEST GENERATION:\n"
            "- Focus on generating high-quality, idiomatic unit/integration tests.\n"
            "- If a dedicated test file already exists among the provided paths, update it.\n"
            "- Otherwise, you MAY propose a new test file in the same directory, following "
            "reasonable naming conventions (e.g., Component.test.tsx, component.spec.ts, "
            "filename.test.js, etc.).\n"
            "- Make tests runnable with the likely test framework based on existing imports.\n"
        )

    user_payload: Dict[str, Any] = {
        "task": task_message,
        "workspace_root": workspace_root,
        "files": files,
    }
    if diagnostics:
        user_payload["diagnostics"] = diagnostics

    completion = await openai_client.chat.completions.create(
        model=model_name,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": base_prompt},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        temperature=0.2,
    )
    raw = completion.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    summary = (parsed.get("summary") or "").strip()
    edits_raw = parsed.get("edits") or []

    normalized_edits: List[Dict[str, Any]] = []
    for item in edits_raw:
        path = item.get("path")
        new_content = item.get("newContent")
        if not path or not isinstance(path, str) or not isinstance(new_content, str):
            continue
        normalized_edits.append(
            {
                "path": path,
                "newContent": new_content,
                "description": (item.get("description") or "").strip() or None,
            }
        )

    return summary, normalized_edits


# Directories we almost never want to read for summaries
_REPO_SUMMARY_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    ".turbo",
    ".idea",
    ".vscode",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "out",
}


# Files we *especially* want to look at if present
_REPO_SUMMARY_KEY_FILES = [
    "README.md",
    "readme.md",
    "README",
    "package.json",
    "pnpm-workspace.yaml",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "setup.cfg",
    "setup.py",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "go.mod",
    # Common monorepo layouts
    "apps/web/package.json",
    "apps/app/package.json",
    "frontend/package.json",
    "backend/pyproject.toml",
]


def _infer_lang_from_suffix(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".md": "markdown",
        ".json": "json",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "javascript",
        ".py": "python",
        ".java": "java",
        ".cs": "csharp",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
    }.get(ext, "")


def _build_repo_layout_section(root: Path) -> str:
    """Return a lightweight 'tree' of the first-level layout."""
    lines: list[str] = []
    try:
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            name = child.name
            if name in _REPO_SUMMARY_EXCLUDED_DIRS:
                continue
            if child.is_dir():
                lines.append(f"- `/`{name}/ (dir)")
            else:
                lines.append(f"- `{name}` (file)")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to walk repo root for layout summary: %s", e)
    return "\n".join(lines) if lines else "_(no files visible at root)_"


def _collect_repo_summary_files(root: Path, max_files: int = 50) -> list[Path]:
    """Select a small set of interesting files to feed into the summary prompt."""
    files: list[Path] = []

    # 1) Prioritize explicit key files
    for rel in _REPO_SUMMARY_KEY_FILES:
        candidate = root / rel
        if candidate.is_file():
            files.append(candidate)
            if len(files) >= max_files:
                return files

    # 2) If still under limit, add a few extra source entrypoints
    #    (shallow search, not a full walk)
    try:
        src_candidates: list[Path] = []
        for sub in ("app", "apps", "src"):
            subdir = root / sub
            if not subdir.is_dir():
                continue
            for child in subdir.glob("**/*"):
                if not child.is_file():
                    continue
                if child.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx", ".py"}:
                    continue
                # Skip test files to keep things focused
                name_lower = child.name.lower()
                if "test" in name_lower or "spec" in name_lower:
                    continue
                src_candidates.append(child)
                if len(src_candidates) >= max_files:
                    break
            if len(src_candidates) >= max_files:
                break

        for p in src_candidates:
            if p not in files:
                files.append(p)
                if len(files) >= max_files:
                    break
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to collect extra source files for repo summary: %s", e)

    return files


def build_repo_snapshot_markdown(
    workspace_root: str,
    max_files: int = 50,
    max_bytes_per_file: int = 8_000,
) -> str:
    """
    Build a compact markdown snapshot of the repo:
    - repo name + path
    - top-level layout
    - contents of a few key files (truncated)
    """
    root = Path(workspace_root)
    repo_name = root.name

    header = (
        f"# Repository snapshot for `{repo_name}`\n\n"
        f"- Absolute path: `{str(root)}`\n\n"
        "## Top-level layout\n\n"
    )

    layout = _build_repo_layout_section(root)

    body_sections: list[str] = []
    selected_files = _collect_repo_summary_files(root, max_files=max_files)

    for p in selected_files:
        try:
            raw = p.read_bytes()[:max_bytes_per_file]
            text = raw.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to read %s for repo snapshot: %s", p, e)
            continue

        lang = _infer_lang_from_suffix(p)
        fence = f"```{lang}" if lang else "```"
        rel = p.relative_to(root)
        body_sections.append(
            f"\n\n---\n\n" f"### File: `{rel}`\n\n" f"{fence}\n{text}\n```"
        )

    snapshot = header + layout + "".join(body_sections)
    return snapshot


def build_repo_tree_markdown(
    root: Path,
    max_depth: int = 2,
    max_entries_per_dir: int = 20,
) -> str:
    """
    Build a compact tree-like listing of the repo up to `max_depth`.

    Example:

    - app/ (dir)
      - page.tsx
      - layout.tsx
    - backend/ (dir)
      - src/
      - tests/
    - package.json
    """

    lines: list[str] = []

    def visit(dir_path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(list(dir_path.iterdir()), key=lambda p: p.name.lower())
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to list %s: %s", dir_path, e)
            return

        count = 0
        for child in children:
            name = child.name
            if name in _REPO_SUMMARY_EXCLUDED_DIRS:
                continue

            prefix = "  " * depth + "- "
            if child.is_dir():
                lines.append(f"{prefix}{name}/ (dir)")
                if depth < max_depth:
                    visit(child, depth + 1)
            else:
                # Only include "interesting" files in the tree to keep it small
                ext = child.suffix.lower()
                if ext in {
                    ".ts",
                    ".tsx",
                    ".js",
                    ".jsx",
                    ".py",
                    ".java",
                    ".cs",
                    ".go",
                } or name in {
                    "package.json",
                    "pyproject.toml",
                    "requirements.txt",
                    "pom.xml",
                    "build.gradle",
                    "Cargo.toml",
                    "go.mod",
                    "Dockerfile",
                    "docker-compose.yml",
                    "next.config.js",
                    "next.config.mjs",
                    "tsconfig.json",
                }:
                    rel = child.relative_to(root)
                    lines.append(f"{prefix}{rel}")
            count += 1
            if count >= max_entries_per_dir:
                lines.append("  " * (depth + 1) + "- …")
                break

    visit(root, depth=0)
    return "\n".join(lines) if lines else "_(no visible structure)_"


_ENTRYPOINT_FILE_NAMES = {
    # Frontend
    "app/page.tsx",
    "app/page.ts",
    "app/layout.tsx",
    "app/layout.ts",
    "pages/index.tsx",
    "pages/index.ts",
    "src/main.tsx",
    "src/main.ts",
    "src/index.tsx",
    "src/index.ts",
    "src/index.js",
    # Node / backend
    "src/server.ts",
    "src/server.js",
    "server.ts",
    "server.js",
    "index.ts",
    "index.js",
    "src/app.ts",
    "src/app.js",
    # Python
    "main.py",
    "app.py",
    "manage.py",
    # Java
    "src/main/java",
}


def find_repo_entrypoints(root: Path) -> list[dict[str, str]]:
    """
    Heuristically find likely 'entrypoint' files and directories.

    Returns a list of { "path": "...", "reason": "..." }.
    """
    entrypoints: list[dict[str, str]] = []

    def add(p: Path, reason: str) -> None:
        try:
            rel = str(p.relative_to(root))
        except Exception:
            rel = str(p)
        entrypoints.append({"path": rel, "reason": reason})

    # 1) Explicit filename matches
    for rel in _ENTRYPOINT_FILE_NAMES:
        candidate = root / rel
        if candidate.is_file() or candidate.is_dir():
            if "app/page" in rel or "pages/index" in rel:
                reason = "Likely main Next.js / React route entrypoint"
            elif "src/main" in rel or "src/index" in rel:
                reason = "Likely main SPA/React entrypoint"
            elif "server" in rel or "app." in rel or "index." in rel:
                reason = "Likely backend/server start file"
            elif rel.endswith("main.py") or rel.endswith("app.py"):
                reason = "Likely Python application entrypoint"
            elif rel.endswith("manage.py"):
                reason = "Likely Django management/entry script"
            elif rel.endswith("src/main/java"):
                reason = "Java application main source root"
            else:
                reason = "Likely entrypoint based on name/location"
            add(candidate, reason)

    # 2) Scripts from package.json
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            import json

            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts") or {}
            for script_name, script_cmd in scripts.items():
                if not isinstance(script_cmd, str):
                    continue
                if any(k in script_cmd for k in ("next dev", "next start")):
                    add(pkg, f"`npm run {script_name}` → Next.js app entry")
                elif any(
                    k in script_cmd
                    for k in ("vite", "react-scripts", "webpack-dev-server")
                ):
                    add(pkg, f"`npm run {script_name}` → frontend dev entry")
                elif "node " in script_cmd or "ts-node " in script_cmd:
                    add(pkg, f"`npm run {script_name}` → Node backend/CLI entry")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to inspect package.json for entrypoints: %s", e)

    return entrypoints


def find_interesting_files(root: Path, max_files: int = 100) -> list[Path]:
    """
    Walk the repo and pick a limited set of 'interesting' files to show
    to the LLM: README, package.json, config, representative code files, etc.
    """
    priority_names = {
        "README",
        "README.md",
        "readme.md",
        "readme",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "pom.xml",
        "build.gradle",
        "settings.gradle",
        "next.config.js",
        "next.config.mjs",
        "tsconfig.json",
        "Dockerfile",
        "docker-compose.yml",
    }

    code_exts = {".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".cs", ".go"}
    selected: list[Path] = []

    # We collect two buckets so we can prefer important meta files first,
    # then add some representative code.
    meta_files: list[Path] = []
    code_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in _REPO_SUMMARY_EXCLUDED_DIRS]

        dir_path = Path(dirpath)
        for fname in filenames:
            full = dir_path / fname

            # Skip huge files (likely binaries, logs, etc.)
            try:
                if full.stat().st_size > 512 * 1024:  # 512 KB
                    continue
            except Exception:
                pass

            if fname in priority_names:
                meta_files.append(full)
            else:
                ext = full.suffix.lower()
                if ext in code_exts:
                    # Avoid tests for the first pass
                    lower = fname.lower()
                    if "test" in lower or "spec" in lower:
                        continue
                    code_files.append(full)

            if len(meta_files) + len(code_files) >= max_files * 2:
                break
        if len(meta_files) + len(code_files) >= max_files * 2:
            break

    # Compose final list: meta first, then some code files
    for f in meta_files:
        if len(selected) >= max_files:
            break
        selected.append(f)

    for f in code_files:
        if len(selected) >= max_files:
            break
        selected.append(f)

    return selected


def _guess_language_tag(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".ts": "ts",
        ".tsx": "tsx",
        ".js": "js",
        ".jsx": "jsx",
        ".py": "python",
        ".java": "java",
        ".cs": "csharp",
        ".go": "go",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".md": "md",
    }.get(ext, "")


def collect_repo_context(
    root: Path,
    max_files: int = 24,
    max_chars_per_file: int = 4000,
) -> tuple[str, str]:
    """
    Return (tree_markdown, files_markdown) for the repo.

    - tree_markdown: folder/file structure
    - files_markdown: headings + code blocks for interesting files
    """
    tree_md = build_repo_tree_markdown(root)

    files = find_interesting_files(root, max_files=max_files)
    file_chunks: list[str] = []

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            try:
                text = path.read_text(errors="ignore")
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to read %s: %s", path, e)
                continue

        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file]

        try:
            rel = path.relative_to(root)
        except Exception:
            rel = path

        lang = _guess_language_tag(path)
        fence = f"```{lang}" if lang else "```"

        file_chunks.append(f"### {rel}\n\n{fence}\n{text}\n```")

    files_md = (
        "\n\n".join(file_chunks)
        if file_chunks
        else "_(no interesting files could be read)_"
    )
    return tree_md, files_md


async def _run_command_in_repo(
    cmd: List[str],
    cwd: Path,
    timeout: int = 180,
) -> Tuple[int, str]:
    """
    Run a shell command in the repo and capture combined stdout+stderr.
    """
    logger.info("[NAVI-REPO] Running command in %s: %s", cwd, " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=PIPE,
        stderr=STDOUT,
    )

    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, f"Command {' '.join(cmd)} timed out after {timeout}s."

    text = out.decode("utf-8", "ignore")
    return proc.returncode or -1, text


def _detect_diagnostics_command(root: Path) -> Optional[List[str]]:
    """
    Best-effort detection of a 'check errors' command for this repo.

    Priority:
      1. package.json scripts: lint, test, build (Node/TS/Next apps)
      2. pytest for Python repos
      3. None if we can't guess.
    """
    commands = _detect_repo_diagnostic_commands(str(root))
    if commands:
        return commands[0]
    return None


def _collect_repo_snapshot(root: Path, max_files: int = 500) -> tuple[str, list[Path]]:
    """
    Walks the repo under `root` and returns:
      - structure_md: markdown list of directories + files
      - key_files: list of Path objects to read for content

    Enhanced to scan more files for comprehensive project understanding.
    """
    logger.info("[NAVI-REPO] _collect_repo_snapshot starting for root=%s", root)
    dir_entries: list[str] = []
    all_files: list[Path] = []

    # Extended code file extensions for thorough analysis (50+ languages)
    CODE_EXTENSIONS = {
        # JavaScript/TypeScript ecosystem
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        # Python
        ".py",
        ".pyw",
        ".pyi",  # .pyi for type stubs
        # JVM languages
        ".java",
        ".kt",
        ".kts",
        ".scala",
        ".groovy",
        ".clj",
        ".cljs",
        ".cljc",
        # Go
        ".go",
        # Rust
        ".rs",
        # Ruby
        ".rb",
        ".rake",
        ".erb",
        # PHP
        ".php",
        ".phtml",
        # .NET / C#
        ".cs",
        ".fs",
        ".fsx",
        ".vb",
        # C/C++
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".cc",
        ".cxx",
        ".hxx",
        # Swift / Objective-C
        ".swift",
        ".m",
        ".mm",
        # Frontend frameworks
        ".vue",
        ".svelte",
        ".astro",
        # GraphQL
        ".graphql",
        ".gql",
        # SQL
        ".sql",
        ".psql",
        ".plsql",
        # Shell scripts
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        # Data Science / ML
        ".r",
        ".R",
        ".jl",
        ".ipynb",  # R, Julia, Jupyter
        # Functional languages
        ".ex",
        ".exs",  # Elixir
        ".hs",
        ".lhs",  # Haskell
        ".erl",
        ".hrl",  # Erlang
        ".ml",
        ".mli",  # OCaml
        ".elm",  # Elm
        # Mobile
        ".dart",  # Flutter/Dart
        # Scripting
        ".lua",
        ".pl",
        ".pm",  # Lua, Perl
        # Systems programming
        ".zig",
        ".nim",
        ".v",  # Zig, Nim, V
        # Web markup/styling
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
        # Config as code
        ".hcl",
        ".tf",
        ".tfvars",  # Terraform
        ".jsonnet",
        ".libsonnet",  # Jsonnet
        ".dhall",  # Dhall
        # Data formats (useful for understanding config)
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".xml",
        # Documentation
        ".md",
        ".mdx",
        ".rst",  # Markdown, MDX, reStructuredText
        # Build/CI config
        ".dockerfile",
        ".containerfile",
        # WebAssembly
        ".wat",
        ".wast",
    }

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            logger.info(
                "[NAVI-REPO] Walking directory: %s (dirs=%s, files=%s)",
                dirpath,
                len(dirnames),
                len(filenames),
            )
            # Filter ignored directories in place so os.walk doesn't descend into them
            dirnames[:] = [d for d in dirnames if d not in REPO_EXPLAIN_IGNORE_DIRS]

            rel_dir = Path(dirpath).relative_to(root)
            rel_dir_str = "." if rel_dir == Path(".") else str(rel_dir)
            dir_entries.append(f"- {rel_dir_str}/")

            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in REPO_EXPLAIN_IGNORE_EXTS:
                    continue

                full_path = Path(dirpath) / fname
                rel_path = full_path.relative_to(root)

                try:
                    size = full_path.stat().st_size
                except OSError:
                    size = 0

                dir_entries.append(f"  - {rel_path} ({size} bytes)")
                all_files.append(full_path)

                if len(all_files) >= max_files:
                    break

            if len(all_files) >= max_files:
                break

    except Exception as e:
        logger.error("[NAVI-REPO] Error during os.walk: %s", e, exc_info=True)
        return "Error scanning directory", []

    logger.info(
        "[NAVI-REPO] Collected %d total files, %d directory entries",
        len(all_files),
        len(dir_entries),
    )

    # Pick "key" files: well-known config/doc names first
    key_files: list[Path] = []
    name_to_file: dict[str, Path] = {}
    for f in all_files:
        # First occurrence of a name wins
        name_to_file.setdefault(f.name, f)

    for key_name in REPO_EXPLAIN_KEY_FILENAMES:
        f = name_to_file.get(key_name)
        if f is not None:
            key_files.append(f)

    # Priority directories for source code discovery
    PRIORITY_DIRS = {
        "app/",
        "src/",
        "pages/",
        "components/",
        "api/",
        "lib/",
        "utils/",
        "services/",
        "hooks/",
        "routes/",
        "controllers/",
        "models/",
        "views/",
        "handlers/",
        "middleware/",
        "core/",
        "modules/",
        "features/",
        "domains/",
        "backend/",
        "frontend/",
        "server/",
        "client/",
    }

    # Collect source code files from priority directories
    priority_code_files: list[Path] = []
    other_code_files: list[Path] = []

    for f in all_files:
        rel = f.relative_to(root)
        rel_str = str(rel)
        ext = f.suffix.lower()

        if ext not in CODE_EXTENSIONS:
            continue

        # Check if in priority directory
        is_priority = any(pdir in rel_str for pdir in PRIORITY_DIRS)

        if is_priority:
            priority_code_files.append(f)
        else:
            other_code_files.append(f)

    # Sort by file size (prefer smaller files that are likely more focused)
    def get_file_size(p: Path) -> int:
        try:
            return p.stat().st_size
        except OSError:
            return 0

    priority_code_files.sort(key=get_file_size)
    other_code_files.sort(key=get_file_size)

    # Add priority code files first (up to 70 from priority directories)
    for f in priority_code_files:
        if f not in key_files:
            key_files.append(f)
            if len(key_files) >= 70:
                break

    # Add other code files if we still have room (up to 100 total)
    if len(key_files) < 100:
        for f in other_code_files:
            if f not in key_files:
                key_files.append(f)
                if len(key_files) >= 100:
                    break

    logger.info(
        "[NAVI-REPO] Selected %d key files for analysis: %s",
        len(key_files),
        [str(f.relative_to(root)) for f in key_files[:10]]
        + (["..."] if len(key_files) > 10 else []),
    )

    structure_md = "\n".join(dir_entries) if dir_entries else "(empty repo?)"
    return structure_md, key_files


def _extract_code_signatures(text: str, file_ext: str) -> list[str]:
    """
    Extract function/class signatures from code for better understanding of large files.
    Returns a list of signature strings.
    """
    import re

    signatures = []

    # Python signatures
    if file_ext in {".py", ".pyw", ".pyi"}:
        # Classes
        for match in re.finditer(r"^class\s+(\w+)(?:\([^)]*\))?:", text, re.MULTILINE):
            signatures.append(f"class {match.group(1)}")
        # Functions/methods
        for match in re.finditer(
            r"^(?:async\s+)?def\s+(\w+)\s*\([^)]*\)(?:\s*->\s*[^:]+)?:",
            text,
            re.MULTILINE,
        ):
            signatures.append(f"def {match.group(1)}()")

    # TypeScript/JavaScript signatures
    elif file_ext in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        # Exported functions
        for match in re.finditer(
            r"^export\s+(?:async\s+)?function\s+(\w+)", text, re.MULTILINE
        ):
            signatures.append(f"export function {match.group(1)}()")
        # Exported classes
        for match in re.finditer(r"^export\s+class\s+(\w+)", text, re.MULTILINE):
            signatures.append(f"export class {match.group(1)}")
        # Exported const components/functions
        for match in re.finditer(r"^export\s+const\s+(\w+)\s*[=:]", text, re.MULTILINE):
            signatures.append(f"export const {match.group(1)}")
        # React components
        for match in re.finditer(
            r"^(?:export\s+)?(?:default\s+)?function\s+([A-Z]\w+)\s*\(",
            text,
            re.MULTILINE,
        ):
            signatures.append(f"function {match.group(1)}()")

    # Go signatures
    elif file_ext == ".go":
        for match in re.finditer(
            r"^func\s+(?:\([^)]+\)\s*)?(\w+)\s*\(", text, re.MULTILINE
        ):
            signatures.append(f"func {match.group(1)}()")
        for match in re.finditer(
            r"^type\s+(\w+)\s+(?:struct|interface)", text, re.MULTILINE
        ):
            signatures.append(f"type {match.group(1)}")

    # Rust signatures
    elif file_ext == ".rs":
        for match in re.finditer(
            r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", text, re.MULTILINE
        ):
            signatures.append(f"fn {match.group(1)}()")
        for match in re.finditer(r"^(?:pub\s+)?struct\s+(\w+)", text, re.MULTILINE):
            signatures.append(f"struct {match.group(1)}")
        for match in re.finditer(
            r"^(?:pub\s+)?impl(?:\s+\w+)?\s+(?:for\s+)?(\w+)", text, re.MULTILINE
        ):
            signatures.append(f"impl {match.group(1)}")

    # Java/Kotlin signatures
    elif file_ext in {".java", ".kt", ".kts"}:
        for match in re.finditer(
            r"^(?:public|private|protected)?\s*(?:static\s+)?class\s+(\w+)",
            text,
            re.MULTILINE,
        ):
            signatures.append(f"class {match.group(1)}")
        for match in re.finditer(
            r"^(?:public|private|protected)?\s*(?:static\s+)?(?:fun|void|\w+)\s+(\w+)\s*\(",
            text,
            re.MULTILINE,
        ):
            signatures.append(f"fun {match.group(1)}()")

    return signatures[:30]  # Limit to top 30 signatures


def _extract_imports(text: str, file_ext: str) -> list[str]:
    """Extract import statements from code."""
    import re

    imports = []

    if file_ext in {".py", ".pyw", ".pyi"}:
        for match in re.finditer(
            r"^(?:from\s+\S+\s+)?import\s+.+$", text, re.MULTILINE
        ):
            imports.append(match.group(0).strip())

    elif file_ext in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        for match in re.finditer(r"^import\s+.+$", text, re.MULTILINE):
            imports.append(match.group(0).strip())

    elif file_ext == ".go":
        for match in re.finditer(
            r'^import\s+(?:\(\s*)?("[^"]+"|[\w/]+)', text, re.MULTILINE
        ):
            imports.append(match.group(0).strip())

    return imports[:20]  # Limit to top 20 imports


def _read_file_snippet(path: Path, max_chars: int = 3000) -> str:
    """
    Returns a UTF-8 text snippet from a file (with truncation and basic safety).
    Increased max_chars for more comprehensive code understanding.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        return f"<<Failed to read {path.name}: {e}>>"

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def _read_file_smart(path: Path, max_chars: int = 5000) -> str:
    """
    Intelligently reads a file, extracting signatures and key content for large files.
    For small files (<=max_chars), returns full content.
    For large files, returns: imports + signatures + truncated content.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        return f"<<Failed to read {path.name}: {e}>>"

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    file_ext = path.suffix.lower()
    total_lines = text.count("\n") + 1

    # Small files: return full content
    if len(text) <= max_chars:
        return text

    # Large files: extract structure + truncated content
    result_parts = []

    # Add file stats
    result_parts.append(f"# File: {path.name} ({total_lines} lines, {len(text)} chars)")

    # Extract and add imports
    imports = _extract_imports(text, file_ext)
    if imports:
        result_parts.append("\n## Imports:")
        result_parts.extend(imports[:10])

    # Extract and add signatures
    signatures = _extract_code_signatures(text, file_ext)
    if signatures:
        result_parts.append("\n## Code Structure (functions/classes):")
        for sig in signatures[:20]:
            result_parts.append(f"  - {sig}")

    # Add truncated content (first portion)
    first_portion_size = max_chars // 2
    result_parts.append(f"\n## Content (first {first_portion_size} chars):")
    result_parts.append(text[:first_portion_size])
    result_parts.append(
        f"\n...[{len(text) - first_portion_size} more chars truncated]..."
    )

    return "\n".join(result_parts)


def detect_project_commands(root: Path) -> Dict[str, Any]:
    """
    Detects the project type from files in `root` and returns a dict:
      {
        "kind": "node" | "python" | "unknown",
        "commands": [
            {"label": "npm test", "cmd": ["npm", "test"]},
            ...
        ],
      }
    """
    kind = "unknown"
    commands: List[Dict[str, Any]] = []

    pkg = root / "package.json"
    if pkg.exists():
        kind = "node"
        scripts: Dict[str, Any] = {}
        try:
            scripts = (
                json.loads(pkg.read_text(encoding="utf-8", errors="ignore")).get(
                    "scripts", {}
                )
                or {}
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to parse package.json in %s: %s", root, e)

        # Prefer lint + test + build if present
        if "lint" in scripts:
            commands.append({"label": "npm run lint", "cmd": ["npm", "run", "lint"]})
        if "test" in scripts:
            commands.append({"label": "npm test", "cmd": ["npm", "test"]})
        if "build" in scripts:
            commands.append({"label": "npm run build", "cmd": ["npm", "run", "build"]})

        # Fallback: at least try npm test if nothing else
        if not commands:
            commands.append({"label": "npm test", "cmd": ["npm", "test"]})

        return {"kind": kind, "commands": commands}

    # Python-style repo
    if (
        (root / "pyproject.toml").exists()
        or (root / "requirements.txt").exists()
        or (root / "Pipfile").exists()
    ):
        kind = "python"

        # Prefer pytest if there is a tests/ dir
        if (root / "pytest.ini").exists() or (root / "tests").exists():
            commands.append({"label": "pytest", "cmd": ["pytest"]})
        else:
            commands.append(
                {"label": "python -m pytest", "cmd": ["python", "-m", "pytest"]}
            )

        return {"kind": kind, "commands": commands}

    # TODO: extend with Java / Maven, Gradle, etc. as needed
    return {"kind": kind, "commands": commands}


async def run_command_in_workspace(
    cmd: List[str],
    cwd: Path,
    timeout_sec: int = 300,
) -> Dict[str, Any]:
    """
    Runs a shell command in `cwd`, capturing stdout/stderr, exit code, and duration.
    """
    started = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
            cwd=str(cwd),
        )
    except FileNotFoundError:
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "exit_code": None,
            "stdout": "",
            "stderr": f"Command not found: {cmd[0]}",
            "timed_out": False,
            "duration_ms": duration_ms,
        }
    except Exception as e:  # noqa: BLE001
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "exit_code": None,
            "stdout": "",
            "stderr": f"Failed to start command {cmd}: {e}",
            "timed_out": False,
            "duration_ms": duration_ms,
        }

    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        timed_out = True
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
        stdout_bytes, stderr_bytes = b"", b"Command timed out."

    duration_ms = int((time.monotonic() - started) * 1000)

    stdout = (stdout_bytes or b"").decode("utf-8", errors="ignore")
    stderr = (stderr_bytes or b"").decode("utf-8", errors="ignore")

    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
    }


async def handle_repo_scan_fast_path(
    request: ChatRequest,
    workspace_root: str,
) -> ChatResponse:
    """
    Fast-path for 'scan this repo and list the main folders and entrypoints'.

    Uses the local filesystem only; no hard-coded product text.
    """
    root = Path(workspace_root)
    repo_name = root.name

    tree_markdown = build_repo_tree_markdown(root)
    entrypoints = find_repo_entrypoints(root)

    # If OpenAI isn't available, just return the raw tree + entrypoint list
    if not OPENAI_ENABLED or openai_client is None:
        bullet_entries = (
            "\n".join(f"- `{e['path']}` — {e['reason']}" for e in entrypoints)
            or "_No obvious entrypoints detected._"
        )

        msg = (
            f"Here's a quick structural scan of the **{repo_name}** repo at "
            f"`{root}`.\n\n"
            "## Main folders and structure\n\n"
            f"{tree_markdown}\n\n"
            "## Likely entrypoints\n\n"
            f"{bullet_entries}\n\n"
            "_OpenAI is not configured, so this is a raw structural view. You "
            "can ask about any specific folder/file for more detail._"
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[
                {
                    "name": f"{repo_name} (workspace)",
                    "type": "workspace",
                    "url": str(root),
                }
            ],
            reply=msg,
            should_stream=False,
            state={"repo_fast_path": True, "kind": "scan", "degraded": True},
            duration_ms=0,
        )

    started = time.monotonic()

    system_prompt = (
        "You are an autonomous engineering assistant helping a developer "
        "understand the structure of their current repository.\n\n"
        "You are given:\n"
        "- A tree-like listing of the repo (limited depth)\n"
        "- A list of heuristically detected 'entrypoints' with reasons\n\n"
        "Your response MUST be a concise markdown explanation that covers:\n"
        "1. The main top-level folders and what they appear to be responsible for.\n"
        "2. Any obvious sub-areas like `app/`, `src/`, `backend/`, `frontend/`, "
        "   `packages/`, `apps/`, etc.\n"
        "3. A bullet list or small table of the likely entrypoints, with a "
        "   short explanation of what each is probably used for.\n"
        "4. Optional suggestions on where a new engineer should start reading.\n\n"
        "Base your reasoning ONLY on the provided structure and file names. "
        "You may infer reasonable purposes from the names (e.g. `apps/web` "
        "is probably a web frontend), but avoid making up unrelated product "
        "marketing or company context."
    )

    entrypoints_md = (
        "\n".join(f"- `{e['path']}` — {e['reason']}" for e in entrypoints)
        or "_No obvious entrypoints detected from heuristics._"
    )

    user_prompt = (
        f"User question: {request.message!r}\n\n"
        f"Repository root: `{root}` (name: `{repo_name}`)\n\n"
        "## Repo structure (tree)\n\n"
        f"{tree_markdown}\n\n"
        "## Heuristic entrypoints\n\n"
        f"{entrypoints_md}\n"
    )

    model = _resolve_model(request.model)

    try:
        resp = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.error("Repo scan fast-path OpenAI error: %s", e, exc_info=True)

        bullet_entries = (
            "\n".join(f"- `{e['path']}` — {e['reason']}" for e in entrypoints)
            or "_No obvious entrypoints detected._"
        )

        msg = (
            f"Here's a structural scan of the **{repo_name}** repo at `{root}`.\n\n"
            "## Main folders and structure\n\n"
            f"{tree_markdown}\n\n"
            "## Likely entrypoints\n\n"
            f"{bullet_entries}\n\n"
            "_I tried to generate a smarter summary but hit an error calling "
            "the LLM. You can still ask about specific folders/files._"
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[
                {
                    "name": f"{repo_name} (workspace)",
                    "type": "workspace",
                    "url": str(root),
                }
            ],
            reply=msg,
            should_stream=False,
            state={
                "repo_fast_path": True,
                "kind": "scan",
                "llm_error": "LLM generation failed",
            },
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    if not reply:
        reply = (
            f"Here's the structure of the **{repo_name}** repo at `{root}`, "
            "but I wasn't able to produce a strong explanation. Try asking "
            "about a specific folder like `app/`, `src/`, or `backend/`."
        )

    duration_ms = int((time.monotonic() - started) * 1000)

    return ChatResponse(
        content=reply,
        actions=[],
        agentRun=None,
        sources=[
            {
                "name": f"{repo_name} (workspace)",
                "type": "workspace",
                "url": str(root),
            }
        ],
        reply=reply,
        should_stream=False,
        state={"repo_fast_path": True, "kind": "scan"},
        duration_ms=duration_ms,
    )


async def handle_repo_explain_fast_path(
    request: ChatRequest,
    workspace_root: str,
) -> ChatResponse:
    """
    Fast-path for 'explain this repo/project' type requests.

    - Walks the workspace_root directory (skipping heavy/irrelevant dirs).
    - Builds a directory tree snapshot.
    - Reads a handful of key files (package.json, README, app/src code, etc.).
    - Asks the LLM to explain the *actual* repository, grounded in those files.
    """
    root = Path(workspace_root)

    if not root.exists():
        msg = (
            "I tried to explain the current repo, but the workspace root "
            f"`{workspace_root}` does not exist on the backend."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            reply=msg,
            should_stream=False,
            state={
                "repo_fast_path": True,
                "kind": "explain",
                "error": "missing_workspace",
            },
            duration_ms=0,
        )

    logger.info("[NAVI-REPO] Starting repo scan for workspace_root=%s", workspace_root)
    logger.info("[NAVI-REPO] Root path exists: %s", root.exists())
    logger.info("[NAVI-REPO] Root path is_dir: %s", root.is_dir())

    structure_md, key_files = _collect_repo_snapshot(root)

    logger.info(
        "[NAVI-REPO] Explaining repo at %s (files_scanned=%d, key_files=%s)",
        root,
        len(key_files),
        [str(p.relative_to(root)) for p in key_files],
    )
    logger.info("[NAVI-REPO] Structure markdown length: %d", len(structure_md))
    logger.info(
        "[NAVI-REPO] Structure preview: %s",
        structure_md[:200] if structure_md else "EMPTY",
    )

    snippets_parts: list[str] = []
    for f in key_files:
        rel = f.relative_to(root)
        # Use smart reading for better handling of large files
        snippet = _read_file_smart(f, max_chars=5000)
        snippets_parts.append(f"### File: `{rel}`\n```text\n{snippet}\n```")

    files_md = "\n\n".join(snippets_parts)
    if not files_md:
        files_md = "_No file contents were captured (repo may be empty or all files were filtered)._"

    system_prompt = (
        "You are Navi, an autonomous engineering assistant integrated into VS Code.\n\n"
        "You are given a **comprehensive snapshot** of a repository, including:\n"
        "- Its complete directory structure (relative paths).\n"
        "- The contents of configuration files (package.json, tsconfig, etc.).\n"
        "- Representative source code from key directories (app, src, pages, components, api, services, etc.).\n\n"
        "Your job is to provide a **thorough, detailed explanation** of this repository to a developer who just opened it.\n\n"
        "You MUST provide a comprehensive analysis covering ALL 15 sections:\n\n"
        "## 1. Project Overview\n"
        "- Project name and type (web app, API, library, CLI tool, monorepo, etc.)\n"
        "- Main purpose and what problem it solves\n"
        "- Target users/audience\n"
        "- Project maturity (early stage, production-ready, etc.)\n\n"
        "## 2. Tech Stack & Architecture\n"
        "- Framework(s) used (e.g., Next.js 14, React 18, FastAPI, etc.) with versions\n"
        "- Programming languages (TypeScript, Python, etc.)\n"
        "- Architecture pattern (monolith, microservices, serverless, etc.)\n"
        "- Build tools and bundlers (Webpack, Vite, Turbopack, etc.)\n\n"
        "## 3. Project Structure Deep Dive\n"
        "- Explain EACH major directory and its purpose\n"
        "- List key files and what they do\n"
        "- Identify patterns (feature-based, layer-based, domain-driven, etc.)\n\n"
        "## 4. Key Entry Points & Routes\n"
        "- Main entry files (app/page.tsx, index.ts, main.py, etc.)\n"
        "- Route structure and navigation patterns\n"
        "- Server startup and initialization flow\n\n"
        "## 5. API Surface\n"
        "- REST endpoints (list paths and methods)\n"
        "- GraphQL schemas if present\n"
        "- WebSocket or real-time endpoints\n"
        "- API versioning strategy\n\n"
        "## 6. Database & Data Layer\n"
        "- Database type (PostgreSQL, MongoDB, etc.)\n"
        "- ORM/ODM used (Prisma, SQLAlchemy, Mongoose, etc.)\n"
        "- Key models/tables and their relationships\n"
        "- Migration strategy\n\n"
        "## 7. State Management\n"
        "- Client-side state (Redux, Zustand, Context, Jotai, etc.)\n"
        "- Server state management (React Query, SWR, etc.)\n"
        "- Data flow patterns\n\n"
        "## 8. Authentication & Authorization\n"
        "- Auth providers (NextAuth, Clerk, Auth0, custom JWT, etc.)\n"
        "- Session management strategy\n"
        "- Protected routes and middleware\n"
        "- Role-based access control if present\n\n"
        "## 9. Core Components & Features\n"
        "- List major components/modules and their responsibilities\n"
        "- Reusable utilities, hooks, and helpers\n"
        "- Third-party integrations\n\n"
        "## 10. Configuration & Environment\n"
        "- Environment variables needed (list ALL from .env.example)\n"
        "- Build/dev configurations\n"
        "- Feature flags if present\n\n"
        "## 11. Testing Strategy\n"
        "- Test framework(s) used (Jest, Pytest, Vitest, etc.)\n"
        "- Test directory structure\n"
        "- Types of tests (unit, integration, e2e)\n"
        "- Coverage requirements\n\n"
        "## 12. Build & Deployment\n"
        "- Build scripts and commands\n"
        "- CI/CD configuration (GitHub Actions, GitLab CI, etc.)\n"
        "- Docker/containerization setup\n"
        "- Deployment target (Vercel, AWS, GCP, etc.)\n\n"
        "## 13. Code Patterns & Conventions\n"
        "- Naming conventions observed\n"
        "- File organization patterns\n"
        "- Notable coding patterns (hooks, HOCs, decorators, etc.)\n"
        "- Error handling patterns\n\n"
        "## 14. Performance Considerations\n"
        "- Caching strategies (Redis, in-memory, etc.)\n"
        "- Code splitting and lazy loading\n"
        "- Image optimization\n"
        "- Rate limiting\n\n"
        "## 15. Getting Started\n"
        "- Prerequisites (Node version, Python version, etc.)\n"
        "- Step-by-step setup instructions\n"
        "- Common development commands\n"
        "- Troubleshooting tips\n\n"
        "IMPORTANT GUIDELINES:\n"
        "- Be SPECIFIC - reference actual file paths and code you see\n"
        "- Do NOT use vague language like 'the snapshot is limited'\n"
        "- Quote relevant code snippets when explaining functionality\n"
        "- If a section doesn't apply, briefly explain why (e.g., 'No database detected')\n"
        "- Mention any security considerations or potential issues you spot"
    )

    user_prompt = (
        f"Workspace root: `{root}`\n\n"
        "## Directory structure (relative paths)\n"
        f"{structure_md}\n\n"
        "## Key file contents\n"
        f"{files_md}\n\n"
        f"User question: {request.message!r}\n\n"
        "Now write a detailed, repo-specific explanation following the system instructions."
    )

    model = _resolve_model(request.model)

    # Fallback if OpenAI is disabled
    if not OPENAI_ENABLED or openai_client is None:
        msg = (
            "OpenAI is not configured on the backend, so I can't generate a natural language "
            "summary yet. Here is the raw snapshot instead:\n\n"
            "## Directory structure\n"
            f"{structure_md}\n\n"
            "## Key file contents\n"
            f"{files_md}\n"
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            reply=msg,
            should_stream=False,
            state={"repo_fast_path": True, "kind": "explain", "degraded": True},
            duration_ms=0,
        )

    started = time.monotonic()
    try:
        resp = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.error("Repo explain fast-path OpenAI error: %s", e, exc_info=True)
        reply = (
            "I hit an error while using the LLM to summarize the repo, but here is the "
            "raw snapshot you can use:\n\n"
            "## Directory structure\n"
            f"{structure_md}\n\n"
            "## Key file contents\n"
            f"{files_md}\n"
        )

    if not reply:
        reply = (
            "I inspected the repo but couldn't produce a confident explanation. "
            "Here is the snapshot instead:\n\n"
            "## Directory structure\n"
            f"{structure_md}\n\n"
            "## Key file contents\n"
            f"{files_md}\n"
        )

    duration_ms = int((time.monotonic() - started) * 1000)
    return ChatResponse(
        content=reply,
        actions=[],
        agentRun=None,
        sources=[],
        reply=reply,
        should_stream=False,
        state={"repo_fast_path": True, "kind": "explain"},
        duration_ms=duration_ms,
    )


async def handle_repo_diagnostics_fast_path(
    request: ChatRequest,
    workspace_root: Optional[str],
) -> ChatResponse:
    if not workspace_root:
        msg = (
            "I can only run diagnostics when a workspace is open.\n"
            "Please open a folder in VS Code and try 'Check errors & fix' again."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"diagnostics_fast_path": True, "error": "no_workspace"},
            duration_ms=0,
        )

    if not OPENAI_ENABLED or openai_client is None:
        msg = (
            "Diagnostics fixing requires the OpenAI backend, but OPENAI_API_KEY is not configured.\n"
            "Once it's set on the backend, I can run tests/lint and propose concrete fixes."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"diagnostics_fast_path": True, "error": "openai_disabled"},
            duration_ms=0,
        )

    started = time.monotonic()

    # 1) Run diagnostics
    diagnostics = await _collect_repo_diagnostics(workspace_root)
    raw_diag = diagnostics.get("raw") or ""
    commands = diagnostics.get("commands") or []

    if not commands:
        msg = (
            "I couldn't find any diagnostics commands to run.\n"
            "Try adding lint/test scripts in package.json (e.g. `npm run lint`, `npm test`), "
            "then run 'Check errors & fix' again."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"diagnostics_fast_path": True, "error": "no_commands"},
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    # 2) Extract error files to focus on
    error_files = _extract_error_files_from_diagnostics(raw_diag, workspace_root)

    # 3) Load file contents
    files_for_model: List[Dict[str, Any]] = []
    root = Path(workspace_root)
    for rel in error_files:
        file_path = root / rel
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        files_for_model.append(
            {
                "kind": "file",
                "path": rel,
                "language": None,  # optional; model can infer
                "content": text,
            }
        )

    if not files_for_model:
        msg = (
            "I ran diagnostics but couldn't map the errors to specific files.\n\n"
            "Here is the diagnostics output:\n\n"
            f"```text\n{raw_diag[:4000]}\n```"
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"diagnostics_fast_path": True, "error": "no_files"},
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    # 4) Ask the model for concrete edits
    summary, edits = await _generate_edits_with_llm(
        model_name=_resolve_model(request.model),
        workspace_root=workspace_root,
        task_message=(
            request.message
            or "Fix the errors reported by diagnostics so that lint/tests pass."
        ),
        files=files_for_model,
        diagnostics=raw_diag,
        mode="diagnostics",
    )

    if not edits:
        msg = (
            "I analyzed the diagnostics and code, but didn't produce concrete edits.\n\n"
            "Diagnostics output:\n\n"
            f"```text\n{raw_diag[:4000]}\n```"
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"diagnostics_fast_path": True, "error": "no_edits"},
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    if not summary:
        summary = "I ran diagnostics, identified failing files, and proposed edits to fix the errors."

    # Build a nice chat explanation
    lines = [summary, ""]
    lines.append("### Diagnostics commands run")
    for r in commands:
        cmd_str = " ".join(r["cmd"])
        lines.append(f"- `{cmd_str}` (exit {r['exit_code']})")
    lines.append("")
    lines.append("### Proposed edits")
    for idx, edit in enumerate(edits, start=1):
        desc = edit.get("description") or "Update file to address diagnostics."
        lines.append(f"{idx}. **{edit['path']}** – {desc}")

    content = "\n".join(lines)
    actions = _edits_to_actions(edits)
    for r in commands:
        cmd_list = r.get("cmd") if isinstance(r, dict) else None
        if not cmd_list:
            continue
        cmd_str = " ".join(cmd_list)
        actions.append(
            {
                "type": "runCommand",
                "description": f"Re-run diagnostics: {cmd_str}",
                "command": cmd_str,
                "cwd": workspace_root,
            }
        )

    return ChatResponse(
        content=content,
        actions=actions,
        agentRun=None,
        sources=[],
        edits=edits,
        reply=content,
        should_stream=False,
        state={"diagnostics_fast_path": True},
        duration_ms=int((time.monotonic() - started) * 1000),
    )


async def handle_code_edit_fast_path(
    request: ChatRequest,
    workspace_root: Optional[str],
) -> ChatResponse:
    """
    Fast-path for code editing requests.

    Uses the attached file/selection from the VS Code extension and asks
    the LLM to propose concrete edits, returned as structured JSON:

      { path, newContent, description? }

    The extension can then apply these edits directly.
    """
    if not request.attachments:
        msg = (
            "To edit code, I need a file or selection attached from VS Code.\n\n"
            "Try again using the 'Fix this file' or 'Fix selection' quick action so "
            "I get the file contents along with your request."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"code_edit_fast_path": True, "error": "no_attachments"},
            duration_ms=0,
        )

    if not OPENAI_ENABLED or openai_client is None:
        msg = (
            "Code editing requires the OpenAI backend, but OPENAI_API_KEY is not configured.\n"
            "Once it's set on the backend, I can propose concrete edits for your files."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"code_edit_fast_path": True, "error": "openai_disabled"},
            duration_ms=0,
        )

    started = time.monotonic()

    # For now we support multi-file, but most interactions will be 1 file/selection.
    targets: List[Dict[str, Any]] = []
    for att in request.attachments or []:
        targets.append(
            {
                "kind": att.kind,
                "path": att.path,
                "language": att.language,
                "content": att.content,
            }
        )

    # Build a JSON-friendly representation of the editing task for the model.
    # We ask for a strict JSON object so we can parse it safely.
    system_prompt = (
        "You are Navi, an AI pair programmer integrated into VS Code.\n"
        "Your job is to propose concrete code edits for the attached files.\n\n"
        "You MUST respond with a single JSON object of the form:\n"
        "{\n"
        '  "summary": string,           // high-level explanation for the user\n'
        '  "edits": [                  // list of edits to apply\n'
        "    {\n"
        '      "path": string,         // file path, as provided in the input\n'
        '      "newContent": string,   // full new file content AFTER edits\n'
        '      "description"?: string  // optional: what this edit does\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Prefer whole-file replacements (`newContent` is the entire updated file), "
        "  not tiny fragments.\n"
        "- Preserve unrelated code and comments.\n"
        "- Do NOT invent new files unless absolutely necessary; focus on the provided paths.\n"
        "- Ensure the code compiles or runs according to the language conventions.\n"
        "- Do NOT include any markdown, text, or explanation outside of the JSON object.\n"
    )

    user_prompt = {
        "task": request.message,
        "workspace_root": workspace_root,
        "files": targets,
    }

    try:
        completion = await openai_client.chat.completions.create(
            model=_resolve_model(request.model),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_prompt, ensure_ascii=False),
                },
            ],
            temperature=0.2,
        )
        raw = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        logger.error("Code edit fast-path JSON parsing failed: %s", e, exc_info=True)
        msg = (
            "I tried to generate structured edits for your code, but something went wrong "
            "while calling the LLM.\n\n"
            "For now, please try asking again or simplify your request."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"code_edit_fast_path": True, "error": "json_parse_failure"},
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    summary = (parsed.get("summary") or "").strip()
    edits_raw = parsed.get("edits") or []

    # Normalize edits into the simple { path, newContent, description } shape
    normalized_edits: List[Dict[str, Any]] = []
    for item in edits_raw:
        path = item.get("path")
        new_content = item.get("newContent")
        if not path or not isinstance(path, str) or not isinstance(new_content, str):
            continue
        normalized_edits.append(
            {
                "path": path,
                "newContent": new_content,
                "description": (item.get("description") or "").strip() or None,
            }
        )

    if not normalized_edits:
        msg = (
            "I analyzed the code you shared but didn't produce any concrete edits.\n\n"
            "You can try rephrasing the request (for example, 'fix the TypeScript errors "
            "in this file' or 'write Jest tests for this component')."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"code_edit_fast_path": True, "error": "no_edits"},
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    # If no summary was produced, create a generic one.
    if not summary:
        summary = (
            "I've proposed edits for the attached file(s). Review them and apply the ones "
            "you want. I tried to fix issues and improve the code according to your request."
        )

    # Build a nice markdown explanation for the chat UI
    explanation_lines = [summary, ""]
    explanation_lines.append("### Proposed edits")
    for idx, edit in enumerate(normalized_edits, start=1):
        desc = edit.get("description") or "Update file."
        explanation_lines.append(f"{idx}. **{edit['path']}** – {desc}")

    content = "\n".join(explanation_lines)
    actions = _edits_to_actions(normalized_edits)

    return ChatResponse(
        content=content,
        actions=actions,
        agentRun=None,
        sources=[],
        edits=normalized_edits,
        reply=content,
        should_stream=False,
        state={"code_edit_fast_path": True},
        duration_ms=int((time.monotonic() - started) * 1000),
    )


async def handle_generate_tests_fast_path(
    request: ChatRequest,
    workspace_root: Optional[str],
) -> ChatResponse:
    if not request.attachments:
        msg = (
            "To generate tests, I need the file attached from VS Code.\n\n"
            "Use a quick action like 'Generate tests for this file' so I receive the "
            "file path and contents."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"generate_tests_fast_path": True, "error": "no_attachments"},
            duration_ms=0,
        )

    if not OPENAI_ENABLED or openai_client is None:
        msg = (
            "Test generation requires the OpenAI backend, but OPENAI_API_KEY is not configured.\n"
            "Once it's set on the backend, I can generate tests for your files."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"generate_tests_fast_path": True, "error": "openai_disabled"},
            duration_ms=0,
        )

    started = time.monotonic()

    files_for_model = [
        {
            "kind": a.kind,
            "path": a.path,
            "language": a.language,
            "content": a.content,
        }
        for a in (request.attachments or [])
    ]

    summary, edits = await _generate_edits_with_llm(
        model_name=_resolve_model(request.model),
        workspace_root=workspace_root,
        task_message=(
            request.message
            or "Generate high-quality unit/integration tests for this file."
        ),
        files=files_for_model,
        diagnostics=None,
        mode="tests",
    )

    if not edits:
        msg = (
            "I analyzed the file but didn't produce concrete test edits.\n"
            "Try specifying the style (e.g., Jest, Vitest, React Testing Library)."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            edits=[],
            reply=msg,
            should_stream=False,
            state={"generate_tests_fast_path": True, "error": "no_edits"},
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    if not summary:
        summary = "I've generated tests for the attached file. Review and apply them as needed."

    lines = [summary, "", "### Proposed test edits"]
    for idx, edit in enumerate(edits, start=1):
        desc = edit.get("description") or "Add/update tests."
        lines.append(f"{idx}. **{edit['path']}** – {desc}")
    content = "\n".join(lines)
    actions = _edits_to_actions(edits)

    return ChatResponse(
        content=content,
        actions=actions,
        agentRun=None,
        sources=[],
        edits=edits,
        reply=content,
        should_stream=False,
        state={"generate_tests_fast_path": True},
        duration_ms=int((time.monotonic() - started) * 1000),
    )


async def handle_coverage_check_fast_path(
    request: ChatRequest,
    workspace_root: Optional[str],
    db: Session,
    org_id: Optional[str],
) -> ChatResponse:
    if not workspace_root:
        msg = (
            "I can only run coverage checks when a workspace is open.\n"
            "Open a folder in VS Code and try again."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            reply=msg,
            should_stream=False,
            state={"coverage_fast_path": True, "error": "no_workspace"},
            duration_ms=0,
        )

    threshold = _get_coverage_threshold(
        message=request.message or "",
        db=db,
        org_id=org_id,
    )

    commands = _detect_coverage_commands(workspace_root)
    if not commands:
        msg = (
            "I couldn't detect a coverage command for this repo.\n\n"
            "Suggestions:\n"
            "- Add a `coverage` script in package.json (e.g., `jest --coverage`).\n"
            "- For Python, install pytest-cov and run `pytest --cov=.`.\n"
            "- Tell me which test runner you use and I can craft the exact command."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            sources=[],
            reply=msg,
            should_stream=False,
            state={"coverage_fast_path": True, "error": "no_commands"},
            duration_ms=0,
        )

    actions = []
    for cmd in commands:
        actions.append(
            {
                "type": "runCommand",
                "description": f"Run coverage (target {threshold}%)",
                "command": cmd,
                "cwd": workspace_root,
                "meta": {"kind": "coverage", "threshold": threshold},
            }
        )

    reply = (
        f"I can run coverage for this repo and check against **{threshold}%**.\n\n"
        "Pick a command below to run with approval. After it finishes, "
        "I'll report whether coverage meets the threshold."
    )

    return ChatResponse(
        content=reply,
        actions=actions,
        agentRun=None,
        sources=[],
        reply=reply,
        should_stream=False,
        state={"coverage_fast_path": True, "threshold": threshold},
        duration_ms=0,
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class FileAttachment(BaseModel):
    kind: Literal[
        "selection", "currentFile", "pickedFile", "file", "image", "local_file"
    ]
    path: Optional[str] = None  # Optional for images
    language: Optional[str] = None
    content: str
    label: Optional[str] = None  # Display label for images


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model (e.g., gpt-4o-mini, gpt-4.1, gpt-5.1)",
    )
    mode: str = Field(
        default="chat-only",
        description="Mode used by the extension (chat-only | agent-full etc.)",
    )

    # Extra hints from the frontend (currently mostly for logging / future use)
    branch: Optional[str] = Field(
        default=None,
        description="Optional git branch name from the frontend (unused for now).",
    )
    execution: Optional[str] = Field(
        default=None,
        description="Execution mode (plan_propose | plan_and_run).",
    )
    scope: Optional[str] = Field(
        default=None,
        description="Scope hint (this_repo | current_file | service).",
    )
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider hint (openai_navra | openai_byok | anthropic_byok).",
    )

    # VS Code extension attachments with workspace context
    attachments: Optional[List[FileAttachment]] = None
    workspace: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Perfect workspace context from VS Code extension",
    )
    workspace_root: Optional[str] = Field(
        default=None,
        description="VS Code workspace root path for workspace-aware operations",
    )
    user_id: str = Field(
        default="default_user",
        description="Logical user identifier (maps to NAVI memory user_id)",
    )

    # Conversation context for multi-turn conversations
    conversation_id: Optional[str] = Field(
        default=None,
        description="Unique conversation/session ID for tracking multi-turn conversations",
    )
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Recent conversation history (last N messages) for context",
    )


class ChatResponse(BaseModel):
    # Shape that the VS Code extension expects:
    #   - `content` (main text)
    #   - optional `actions` (workspace plan steps)
    #   - optional `agentRun` (for the plan card)
    #   - optional `sources` (for source pills)
    content: str
    actions: List[Dict[str, Any]] = []
    agentRun: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = []  # Add sources field

    # NEW: structured code edits Navi is proposing
    # Each edit: { "path": string, "newContent": string, "description"?: string }
    edits: List[Dict[str, Any]] = []

    # Progress tracking
    status: Optional[str] = None  # Current status message for user
    progress_steps: List[str] = []  # List of completed steps

    # Extra debugging / future features from agent loop; extension ignores these
    reply: Optional[str] = None
    should_stream: Optional[bool] = None
    state: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None

    # NAVI V3: Intelligence fields (like Codex/Claude Code)
    thinking_steps: Optional[List[str]] = None  # Show what NAVI did
    files_read: Optional[List[str]] = None  # Show what files were analyzed
    project_type: Optional[str] = None  # Detected project type
    framework: Optional[str] = None  # Detected framework

    # NAVI V2: Plan mode and approval flow
    requires_approval: bool = False  # Whether user approval is needed
    plan_id: Optional[str] = None  # Unique plan ID for tracking
    actions_with_risk: List[Dict[str, Any]] = []  # Actions with risk assessment


@router.get("/test-agent")
async def test_agent_endpoint():
    """Simple test endpoint so we can sanity-check wiring."""
    return {
        "message": "Agent mode test",
        "agentRun": {
            "steps": [
                {
                    "id": "test-1",
                    "label": "Test step",
                    "detail": "This is a test",
                    "status": "pending",
                }
            ]
        },
    }


@router.get("/debug/openai")
async def debug_openai():
    """Debug endpoint to check OpenAI status."""
    import os

    key = os.getenv("OPENAI_API_KEY", "")
    return {
        "OPENAI_ENABLED": OPENAI_ENABLED,
        "has_key": bool(key),
        "key_prefix": key[:7] if key else "",
        "key_length": len(key) if key else 0,
    }


# ---------------------------------------------------------------------------
# Main chat endpoint
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
@no_type_check
# pyright: ignore[reportGeneralTypeIssues]
async def navi_chat(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Main NAVI chat endpoint used by the VS Code extension.

    - Guards on OPENAI_API_KEY (degraded mode if missing).
    - Calls `run_agent_loop` (7-stage agent OS pipeline).
    - Maps the result into the `{ content, actions, agentRun }` shape the
      VS Code panel expects.
    """
    print(
        f"[TOP-LEVEL-DEBUG] NAVI CHAT ENTRY - message: '{request.message}', workspace_root: '{request.workspace_root}'"
    )

    print(
        f"[NAVI-ENTRY-DEBUG] Received request: message='{request.message[:50]}...', workspace={request.workspace}"
    )
    logger.info(
        "[NAVI-ENTRY-DEBUG] Request received: message=%s, workspace=%s",
        request.message[:50],
        request.workspace,
    )
    if not OPENAI_ENABLED:
        # Still return a `content` field so the extension stays happy
        msg = (
            "Hi! NAVI chat is currently running in degraded mode because "
            "OPENAI_API_KEY is not configured on the backend."
        )
        return ChatResponse(
            content=msg,
            actions=[],
            agentRun=None,
            reply=msg,
            should_stream=False,
            state={"degraded": True},
            duration_ms=0,
        )

    smalltalk_phrases = (
        "how are you",
        "how r u",
        "how are u",
        "howre you",
        "hru",
        "hw r u",
        "hw ar u",
        "what's up",
        "whats up",
        "what is up",
        "wassup",
        "watsup",
        "how are you doing",
        "hello",
        "hellooo",
        "helloo",
        "helo",
        "hell",
        "hi",
        "hii",
        "hiii",
        "hey",
        "heyy",
        "hiya",
        "yo",
        "sup",
        "good morning",
        "good afternoon",
        "good evening",
        "gm",
        "ga",
        "ge",
        "latest news",
        "what's going on",
        "what is going on",
        "news",
    )

    # Phrases that indicate NOT smalltalk (work-related questions)
    work_question_indicators = (
        "project",
        "explain",
        "what does",
        "what is",
        "describe",
        "tell me about",
        "working on",
        "repository",
        "repo",
        "codebase",
        "code",
        "file",
        "function",
        "class",
    )

    try:
        user_id = (request.user_id or "default_user").strip() or "default_user"
        mode = (request.mode or "chat-only").strip() or "chat-only"
        workspace_root = request.workspace_root or (request.workspace or {}).get(
            "workspace_root"
        )
        org_id = http_request.headers.get("x-org-id") if http_request else None

        logger.info(
            "[NAVI-CHAT] user=%s model=%s mode=%s org=%s workspace=%s msg='%s...'",
            user_id,
            request.model,
            mode,
            org_id,
            workspace_root,
            request.message[:80],
        )

        # Debug workspace detection
        logger.info(
            "[NAVI-WORKSPACE-DEBUG] workspace_root=%s, workspace_dict=%s",
            workspace_root,
            request.workspace,
        )
        logger.info("[NAVI-WORKSPACE-DEBUG] request.message=%s", request.message)
        logger.info(
            "[NAVI-WORKSPACE-DEBUG] repo_explain_check=%s",
            _looks_like_repo_explain(request.message),
        )
        logger.info(
            "[NAVI-WORKSPACE-DEBUG] request.workspace_root=%s", request.workspace_root
        )

        # Log workspace detection for debugging
        logger.info("[NAVI-WORKSPACE-DEBUG] Using workspace_root=%s", workspace_root)

        # ------------------------------------------------------------------
        # AUTONOMOUS CODING DETECTION - Removed hardcoded early return
        # Let all code generation requests flow through to the agent loop
        # which uses the actual LLM for intelligent responses
        # ------------------------------------------------------------------
        # NOTE: The previous hardcoded "AUTONOMOUS CODING MODE ACTIVATED" response
        # has been removed. Now all requests go through the agent loop to get
        # actual LLM-generated code and contextual descriptions.

        # NOTE: Project analysis ("how to run" questions) is handled by
        # chat.py using navi_brain.py's ProjectAnalyzer. This /chat endpoint
        # in navi.py is not the primary handler (chat.py is included first).

        # If this is *very short* and clearly small talk (not a work request), reply directly.
        # To avoid false positives (e.g., "which project are we in?"), only trigger when the
        # message is short, matches known greeting phrases, and doesn't contain work indicators.
        msg_lower = request.message.lower().strip()
        is_work_question = any(
            indicator in msg_lower for indicator in work_question_indicators
        )

        if (
            len(msg_lower) <= 60
            and any(p in msg_lower for p in smalltalk_phrases)
            and not _looks_like_jira_my_issues(msg_lower)
            and not is_work_question  # Don't treat work questions as smalltalk
        ):
            how_patterns = ("how are", "how r", "howre", "hru", "hw r", "hw ar")
            whats_up_patterns = (
                "what's up",
                "whats up",
                "what is up",
                "wassup",
                "watsup",
                "sup",
            )
            time_patterns = (
                "good morning",
                "good afternoon",
                "good evening",
                "gm",
                "ga",
                "ge",
            )

            if any(p in msg_lower for p in how_patterns):
                reply = random.choice(
                    [
                        "I’m doing well and ready to help. What do you want to tackle—code, Jira, docs, or builds?",
                        "Doing great—what should we work on next?",
                        "All good here. Want a review, a fix, or a repo scan?",
                    ]
                )
            elif any(p in msg_lower for p in whats_up_patterns) or "news" in msg_lower:
                reply = random.choice(
                    [
                        "All clear on my side. Tell me what you want to work on—code, Jira, docs, or builds.",
                        "Not much—ready to dive in. Want a review or a scan?",
                        "Quiet here. What do you want me to tackle?",
                    ]
                )
            elif any(p in msg_lower for p in time_patterns):
                reply = random.choice(
                    [
                        "Good to see you. What should we work on?",
                        "Hope you're having a good day. What do you need help with?",
                        "Hello! Ready to dive into code or a repo scan?",
                    ]
                )
            else:
                reply = random.choice(
                    [
                        "Hi there—ready when you are. What should we work on—code, Jira, docs, or builds?",
                        "Hey! What would you like to do next?",
                        "Hello! I can review code, fix errors, or sync connectors—what’s up?",
                    ]
                )
            return ChatResponse(
                content=reply,
                actions=[],
                agentRun=None,
                reply=reply,
                should_stream=False,
                state={"smalltalk": True},
                duration_ms=0,
            )

        # Soft guard: log when workspace is missing but do not block response
        has_workspace = bool(workspace_root or request.workspace)
        if not has_workspace:
            logger.warning(
                "Navi chat called without workspace; continuing in limited mode.",
                extra={
                    "workspace_root": workspace_root,
                    "workspace": request.workspace,
                    "user_id": getattr(request, "user_id", None),
                },
            )

        # Git HEAD fast-path: respond clearly when repo is not initialized or has no commits.
        git_head_query = _looks_like_git_head_check(msg_lower)
        git_review_query = _looks_like_git_review_request(msg_lower)
        if (git_head_query or git_review_query) and workspace_root:
            try:
                git_service = GitService(workspace_root)
            except ValueError:
                reply = (
                    "I cannot review changes because this folder does not look like a Git repository.\n\n"
                    "How to fix:\n"
                    "- Open the repo root that contains the `.git` folder.\n"
                    '- Or initialize a repo: `git init`, then `git add -A`, then `git commit -m "Initial commit"`.\n'
                    "- If this is a subfolder, reopen VS Code at the project root.\n\n"
                    "If you want, I can run the Git setup commands once you approve them."
                )
                init_actions = [
                    {
                        "type": "runCommand",
                        "description": "Initialize git repo",
                        "command": "git init",
                        "cwd": workspace_root,
                    },
                    {
                        "type": "runCommand",
                        "description": "Stage all files",
                        "command": "git add -A",
                        "cwd": workspace_root,
                    },
                    {
                        "type": "runCommand",
                        "description": "Create initial commit",
                        "command": 'git commit -m "Initial commit"',
                        "cwd": workspace_root,
                    },
                ]
                return ChatResponse(
                    content=reply,
                    actions=init_actions,
                    agentRun=None,
                    sources=[],
                    reply=reply,
                    should_stream=False,
                    state={"git_fast_path": True, "has_head": False},
                    duration_ms=0,
                )

            if not git_service.has_head():
                reply = (
                    "This repository has no valid HEAD yet (no commits), so I cannot compare against main/HEAD.\n\n"
                    "How to fix:\n"
                    '- Create an initial commit: `git add -A` then `git commit -m "Initial commit"`.\n'
                    "- If you expect a remote main branch: `git fetch origin` then `git checkout main`.\n\n"
                    "If you want, I can run the Git commands below once you approve them."
                )
                head_actions = [
                    {
                        "type": "runCommand",
                        "description": "Check git status",
                        "command": "git status --porcelain",
                        "cwd": workspace_root,
                    },
                    {
                        "type": "runCommand",
                        "description": "Stage all files",
                        "command": "git add -A",
                        "cwd": workspace_root,
                    },
                    {
                        "type": "runCommand",
                        "description": "Create initial commit",
                        "command": 'git commit -m "Initial commit"',
                        "cwd": workspace_root,
                    },
                ]
                return ChatResponse(
                    content=reply,
                    actions=head_actions,
                    agentRun=None,
                    sources=[],
                    reply=reply,
                    should_stream=False,
                    state={"git_fast_path": True, "has_head": False},
                    duration_ms=0,
                )

            if git_head_query:
                repo_name = _get_repo_name_from_path(workspace_root) or "this repo"
                reply = (
                    f"Yes — `{repo_name}` has a valid HEAD commit. You can safely run git diff/review "
                    "against main/HEAD.\n\n"
                    "If you want, I can run git status/log commands to confirm the state."
                )
                head_check_actions = [
                    {
                        "type": "runCommand",
                        "description": "Check git status",
                        "command": "git status --porcelain",
                        "cwd": workspace_root,
                    },
                    {
                        "type": "runCommand",
                        "description": "Show recent commits",
                        "command": "git log --oneline -n 5",
                        "cwd": workspace_root,
                    },
                    {
                        "type": "runCommand",
                        "description": "Verify HEAD",
                        "command": "git rev-parse --verify HEAD",
                        "cwd": workspace_root,
                    },
                ]
                return ChatResponse(
                    content=reply,
                    actions=head_check_actions,
                    agentRun=None,
                    sources=[],
                    reply=reply,
                    should_stream=False,
                    state={"git_fast_path": True, "has_head": True},
                    duration_ms=0,
                )

        git_command = _extract_git_command(request.message)
        inferred = None
        if not git_command:
            inferred = _infer_git_command_from_text(request.message)
            if inferred:
                git_command = inferred.get("command")

        if git_command and not workspace_root:
            reply = (
                "I can run git commands once a workspace is open.\n"
                "Open the repo in VS Code and try again."
            )
            return ChatResponse(
                content=reply,
                actions=[],
                agentRun=None,
                sources=[],
                reply=reply,
                should_stream=False,
                state={"git_command_fast_path": True, "error": "no_workspace"},
                duration_ms=0,
            )

        if git_command and workspace_root:
            if inferred and inferred.get("requires_head"):
                try:
                    git_service = GitService(workspace_root)
                except ValueError:
                    reply = (
                        "I cannot run that git command because this folder does not look like a Git repository.\n\n"
                        "How to fix:\n"
                        "- Open the repo root that contains the `.git` folder.\n"
                        '- Or initialize a repo: `git init`, then `git add -A`, then `git commit -m "Initial commit"`.\n'
                        "- If this is a subfolder, reopen VS Code at the project root.\n\n"
                        "If you want, I can run the Git setup commands once you approve them."
                    )
                    init_actions = [
                        {
                            "type": "runCommand",
                            "description": "Initialize git repo",
                            "command": "git init",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Stage all files",
                            "command": "git add -A",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Create initial commit",
                            "command": 'git commit -m "Initial commit"',
                            "cwd": workspace_root,
                        },
                    ]
                    return ChatResponse(
                        content=reply,
                        actions=init_actions,
                        agentRun=None,
                        sources=[],
                        reply=reply,
                        should_stream=False,
                        state={"git_command_fast_path": True, "has_head": False},
                        duration_ms=0,
                    )

                if not git_service.has_head():
                    reply = (
                        "This repository has no valid HEAD yet (no commits), so I cannot run that comparison.\n\n"
                        "How to fix:\n"
                        '- Create an initial commit: `git add -A` then `git commit -m "Initial commit"`.\n'
                        "- If you expect a remote main branch: `git fetch origin` then `git checkout main`.\n\n"
                        "If you want, I can run the Git commands below once you approve them."
                    )
                    head_actions = [
                        {
                            "type": "runCommand",
                            "description": "Check git status",
                            "command": "git status --porcelain",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Stage all files",
                            "command": "git add -A",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Create initial commit",
                            "command": 'git commit -m "Initial commit"',
                            "cwd": workspace_root,
                        },
                    ]
                    return ChatResponse(
                        content=reply,
                        actions=head_actions,
                        agentRun=None,
                        sources=[],
                        reply=reply,
                        should_stream=False,
                        state={"git_command_fast_path": True, "has_head": False},
                        duration_ms=0,
                    )

            ok, reason = _is_safe_git_command(git_command)
            if not ok:
                reply = (
                    "I can run git commands, but this one looks unsafe or malformed.\n\n"
                    f"Reason: {reason}\n\n"
                    "Try a simple command like `git status`, `git log --oneline -n 5`, "
                    "or wrap the exact command in backticks."
                )
                return ChatResponse(
                    content=reply,
                    actions=[],
                    agentRun=None,
                    sources=[],
                    reply=reply,
                    should_stream=False,
                    state={"git_command_fast_path": True, "error": "unsafe_command"},
                    duration_ms=0,
                )

            description = (
                inferred.get("description")
                if inferred and inferred.get("description")
                else "Run git command"
            )
            reply = (
                f"I can run `{git_command}` in your repo once you approve it.\n\n"
                "Click **Run** to execute, or edit the command and ask again."
            )
            actions = [
                {
                    "type": "runCommand",
                    "description": description,
                    "command": git_command,
                    "cwd": workspace_root,
                }
            ]
            return ChatResponse(
                content=reply,
                actions=actions,
                agentRun=None,
                sources=[],
                reply=reply,
                should_stream=False,
                state={"git_command_fast_path": True, "command": git_command},
                duration_ms=0,
            )

        # Guard: if user mentions Jira but there is no connection, respond directly
        if "jira" in msg_lower and not _looks_like_jira_my_issues(msg_lower):
            # Fallback: if no org_id header, use the most recent Jira connection's org_id
            if not org_id:
                org_id = db.execute(
                    text("SELECT org_id FROM jira_connection ORDER BY id DESC LIMIT 1")
                ).scalar()
            conn_count = (
                db.execute(text("SELECT COUNT(*) FROM jira_connection")).scalar() or 0
            )

            # Check if Jira connector is connected (don't wait for slow sync)
            if conn_count == 0:
                msg = "Jira is not connected. Connect Jira in the Connectors tab and retry."
                return ChatResponse(
                    content=msg,
                    actions=[],
                    agentRun=None,
                    sources=[],
                    reply=msg,
                    should_stream=False,
                    state={"jira_fast_path": True},
                    duration_ms=0,
                )

        # ✅ Jira fast-path: bypass workspace planner for direct tool execution
        jira_match = _looks_like_jira_my_issues(request.message)
        logger.info(
            "[NAVI-CHAT] Checking Jira fast-path for: '%s' -> %s",
            request.message,
            jira_match,
        )

        if jira_match:
            logger.info(
                "[NAVI-CHAT] Using Jira fast-path for message: %s", request.message[:50]
            )

            # Guard: Jira connection present for this org?
            if not org_id:
                org_id = db.execute(
                    text("SELECT org_id FROM jira_connection ORDER BY id DESC LIMIT 1")
                ).scalar()
            conn_count = (
                db.execute(text("SELECT COUNT(*) FROM jira_connection")).scalar() or 0
            )

            # Just check if Jira is connected (don't wait for slow sync)
            if conn_count == 0:
                msg = "Jira is not connected. Connect Jira in the Connectors tab and retry."
                return ChatResponse(
                    content=msg,
                    actions=[],
                    agentRun=None,
                    sources=[],
                    reply=msg,
                    should_stream=False,
                    state={"jira_fast_path": True},
                    duration_ms=0,
                )

            # Track timing
            started = time.monotonic()

            # Create Jira intent
            NaviIntent(
                family=IntentFamily.PROJECT_MANAGEMENT,
                kind=IntentKind.SUMMARIZE_TICKETS,  # Use existing enum value
                raw_text=request.message,
                source=IntentSource.CHAT,
                priority=IntentPriority.NORMAL,
                confidence=0.9,
            )

            context = {
                "message": request.message,
                "user_id": user_id,
                "workspace": request.workspace or {"workspace_root": workspace_root},
            }

            # Direct tool execution with sources
            try:
                tool_result = await execute_tool_with_sources(
                    user_id=user_id,
                    tool_name="jira.list_assigned_issues_for_user",
                    args={"limit": 20, "context": context},
                    db=db,
                )

                # Format response for VS Code
                issues_text = "Here are your Jira issues:\n"
                if tool_result.output:
                    for issue in tool_result.output[:10]:  # Limit to 10 for display
                        key = issue.get("issue_key", "Unknown")
                        summary = issue.get("summary", "No summary")
                        status = issue.get("status", "Unknown")
                        issues_text += f"• **{key}** - {summary} ({status})\n"
                else:
                    issues_text = "No Jira issues found for you."

                # Return direct response with sources
                return ChatResponse(
                    content=issues_text,
                    actions=[],
                    agentRun=None,
                    sources=tool_result.sources,  # Pass through sources for pills
                    reply=issues_text,
                    should_stream=False,
                    state={"jira_fast_path": True},
                    duration_ms=int((time.monotonic() - started) * 1000),
                )

            except Exception as e:
                logger.error("[NAVI-CHAT] Jira fast-path failed: %s", e)
                # Fall through to regular agent loop

        # ✅ Repo fast-path: detect "which repo are we in?" questions
        repo_match = _looks_like_repo_where(request.message)
        logger.info(
            "[NAVI-CHAT] Checking repo fast-path for: '%s' -> %s",
            request.message,
            repo_match,
        )

        # ✅ Repo explain fast-path: detect "explain this repo/project" questions
        repo_explain_match = _looks_like_repo_explain(request.message)
        logger.info(
            "[NAVI-CHAT] Checking repo explain fast-path for: '%s' -> %s",
            request.message,
            repo_explain_match,
        )

        if repo_match:
            logger.info(
                "[NAVI-CHAT] Using repo fast-path for message: %s", request.message[:50]
            )

            # Derive repo info from VS Code workspace context
            repo_root = workspace_root  # This comes from request.workspace_root

            if not repo_root and request.workspace:
                # Fallback: extract from workspace object
                workspace_data = request.workspace
                repo_root = workspace_data.get("workspace_root") or workspace_data.get(
                    "repo_root"
                )

            # Extract repo name from workspace root
            repo_name = None
            if repo_root:
                clean = str(repo_root).rstrip("/\\")
                base = os.path.basename(clean)
                repo_name = base or clean

            # Log the detected repo name for debugging
            logger.info("[NAVI-CHAT] 🚨 Detected repo_name: %r", repo_name)

            logger.info(
                "[NAVI-CHAT] Repo fast-path: workspace_root=%r repo_root=%r repo_name=%r",
                workspace_root,
                repo_root,
                repo_name,
            )

            reply = f"You're currently working in the **{repo_name}** repo."

            return ChatResponse(
                content=reply,
                actions=[],
                agentRun=None,
                sources=[],
                reply=reply,
                should_stream=False,
                state={
                    "repo_fast_path": True,
                    "repo_name": repo_name,
                    "repo_root": repo_root,
                    "kind": "where",
                },
                duration_ms=10,
            )

        # Repo explanation and scan fast-paths, based on local workspace_root
        logger.info(
            "[NAVI-DEBUG] Checking repo explain: workspace_root=%s, msg_lower=%s",
            workspace_root,
            msg_lower[:50],
        )
        logger.info(
            "[NAVI-DEBUG] repo explain match: %s", _looks_like_repo_explain(msg_lower)
        )

        if workspace_root:
            if _looks_like_repo_explain(msg_lower):
                try:
                    logger.info(
                        "[NAVI-CHAT] Using repo explain fast-path for workspace_root=%s",
                        workspace_root,
                    )
                    return await handle_repo_explain_fast_path(
                        request=request,
                        workspace_root=workspace_root,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "[NAVI-CHAT] Repo explain fast-path failed; falling back to agent loop: %s",
                        e,
                        exc_info=True,
                    )

            if _looks_like_repo_scan(msg_lower):
                try:
                    logger.info(
                        "[NAVI-CHAT] Using repo scan fast-path for workspace_root=%s",
                        workspace_root,
                    )
                    return await handle_repo_scan_fast_path(
                        request=request,
                        workspace_root=workspace_root,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "[NAVI-CHAT] Repo scan fast-path failed; falling back to agent loop: %s",
                        e,
                        exc_info=True,
                    )

            if _looks_like_coverage_request(msg_lower):
                try:
                    logger.info(
                        "[NAVI-CHAT] Using coverage fast-path for workspace_root=%s",
                        workspace_root,
                    )
                    return await handle_coverage_check_fast_path(
                        request=request,
                        workspace_root=workspace_root,
                        db=db,
                        org_id=org_id,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "[NAVI-CHAT] Coverage fast-path failed; falling back to agent loop: %s",
                        e,
                        exc_info=True,
                    )

            # Diagnostics fast-path ("Check errors & fix")
            if _looks_like_check_errors(msg_lower):
                try:
                    logger.info(
                        "[NAVI-CHAT] Using diagnostics fast-path for workspace_root=%s",
                        workspace_root,
                    )
                    return await handle_repo_diagnostics_fast_path(
                        request=request,
                        workspace_root=workspace_root,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "[NAVI-CHAT] Diagnostics fast-path failed; falling back to agent loop: %s",
                        e,
                        exc_info=True,
                    )

        # Generate tests fast-path
        if _looks_like_generate_tests(msg_lower) and (request.attachments or []):
            try:
                logger.info(
                    "[NAVI-CHAT] Using generate-tests fast-path for message='%s...'",
                    msg_lower[:60],
                )
                return await handle_generate_tests_fast_path(
                    request=request,
                    workspace_root=workspace_root,
                )
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[NAVI-CHAT] Generate-tests fast-path failed; falling back to agent loop: %s",
                    e,
                    exc_info=True,
                )

        # Generic code-edit fast-path
        if _looks_like_code_edit(msg_lower) and (request.attachments or []):
            try:
                logger.info(
                    "[NAVI-CHAT] Using code-edit fast-path for message='%s...'",
                    msg_lower[:60],
                )
                return await handle_code_edit_fast_path(
                    request=request,
                    workspace_root=workspace_root,
                )
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[NAVI-CHAT] Code-edit fast-path failed; falling back to agent loop: %s",
                    e,
                    exc_info=True,
                )

        # ------------------------------------------------------------------
        # AUTONOMOUS CODING DETECTION - Removed hardcoded early return
        # All code generation requests now flow through to the agent loop
        # which uses the actual LLM for intelligent, contextual responses
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # Call the NAVI agent loop with perfect workspace context
        # ------------------------------------------------------------------
        workspace_data = request.workspace or {}
        if workspace_root:
            workspace_data["workspace_root"] = workspace_root

        # Initialize progress tracker
        progress_tracker = ProgressTracker()
        progress_tracker.update_status("Initializing NAVI agent...")
        progress_tracker.complete_step("Workspace detected")

        # Determine request type and check for code analysis requests
        msg_lower = request.message.lower()

        # Check for code analysis requests and route to comprehensive analysis
        # DISABLED: This was routing to fake synthetic analysis instead of real git diff
        # code_analysis_keywords = [
        #     "analyze",
        #     "review",
        #     "changes",
        #     "code",
        #     "diff",
        #     "git",
        #     "quality",
        #     "security",
        #     "performance",
        # ]
        # is_code_analysis = any(keyword in msg_lower for keyword in code_analysis_keywords)
        is_code_analysis = False  # Force disable fake analysis routing

        print(f"DEBUG NAVI - Message: '{msg_lower}'")
        print(f"DEBUG NAVI - Workspace root: '{workspace_root}'")
        print(f"DEBUG NAVI - Is code analysis: {is_code_analysis}")
        print(
            f"DEBUG NAVI - Should trigger comprehensive: {is_code_analysis and workspace_root}"
        )

        if is_code_analysis and workspace_root:
            print("DEBUG NAVI - ENTERING comprehensive analysis branch")
            try:
                try:
                    git_service = GitService(workspace_root)
                except ValueError:
                    reply = (
                        "I cannot review changes because this folder does not look like a Git repository.\n\n"
                        "How to fix:\n"
                        "- Open the repo root that contains the `.git` folder.\n"
                        '- Or initialize a repo: `git init`, then `git add -A`, then `git commit -m "Initial commit"`.\n'
                        "- If this is a subfolder, reopen VS Code at the project root.\n\n"
                        "If you want, I can run the Git setup commands once you approve them."
                    )
                    init_actions = [
                        {
                            "type": "runCommand",
                            "description": "Initialize git repo",
                            "command": "git init",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Stage all files",
                            "command": "git add -A",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Create initial commit",
                            "command": 'git commit -m "Initial commit"',
                            "cwd": workspace_root,
                        },
                    ]
                    return ChatResponse(
                        content=reply,
                        actions=init_actions,
                        agentRun=None,
                        reply=reply,
                        should_stream=False,
                        state={"git_fast_path": True, "has_head": False},
                        duration_ms=0,
                    )

                if not git_service.has_head():
                    reply = (
                        "This repository has no valid HEAD yet (no commits), so I cannot compare against main/HEAD.\n\n"
                        "How to fix:\n"
                        '- Create an initial commit: `git add -A` then `git commit -m "Initial commit"`.\n'
                        "- If you expect a remote main branch: `git fetch origin` then `git checkout main`.\n\n"
                        "If you want, I can run the Git commands below once you approve them."
                    )
                    head_actions = [
                        {
                            "type": "runCommand",
                            "description": "Check git status",
                            "command": "git status --porcelain",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Stage all files",
                            "command": "git add -A",
                            "cwd": workspace_root,
                        },
                        {
                            "type": "runCommand",
                            "description": "Create initial commit",
                            "command": 'git commit -m "Initial commit"',
                            "cwd": workspace_root,
                        },
                    ]
                    return ChatResponse(
                        content=reply,
                        actions=head_actions,
                        agentRun=None,
                        reply=reply,
                        should_stream=False,
                        state={"git_fast_path": True, "has_head": False},
                        duration_ms=0,
                    )

                # Use streaming SSE endpoint for real-time progress to frontend
                async def generate_analysis_with_stream():
                    from backend.services.review_service import generate_review_stream

                    all_review_entries = []

                    try:
                        async for event in generate_review_stream(workspace_root):
                            event_type = event.get("type")
                            event_data = event.get("data") or {}
                            if not isinstance(event_data, dict):
                                event_data = {}

                            if event_type == "live-progress":
                                # Stream progress updates (canonical schema)
                                yield f"data: {json.dumps({'kind': 'liveProgress', 'step': event_data})}\n\n"
                            elif event_type == "review-entry":
                                # Stream review entries (canonical schema)
                                all_review_entries.append(event_data)
                                yield f"data: {json.dumps({'kind': 'reviewEntry', 'entry': event_data})}\n\n"
                            elif event_type == "done":
                                # Analysis complete
                                break
                            elif event_type == "error":
                                # Stream error (canonical schema)
                                yield f"data: {json.dumps({'kind': 'error', 'message': event_data.get('message')})}\n\n"
                                return

                        # Generate final summary
                        if not all_review_entries:
                            summary = {
                                "kind": "reviewSummary",
                                "message": "✅ No changes detected - your repository is clean!",
                                "totalFiles": 0,
                                "severityCounts": {"high": 0, "medium": 0, "low": 0},
                                "listedFiles": [],
                            }
                        else:
                            severity_counts = {"high": 0, "medium": 0, "low": 0}
                            for entry in all_review_entries:
                                severity = entry.get("severity", "low")
                                severity_counts[severity] = (
                                    severity_counts.get(severity, 0) + 1
                                )

                            summary = {
                                "kind": "reviewSummary",
                                "message": f"Analysis complete - {len(all_review_entries)} files reviewed",
                                "totalFiles": len(all_review_entries),
                                "severityCounts": severity_counts,
                                "listedFiles": [
                                    e.get("file", "unknown")
                                    for e in all_review_entries[:50]
                                ],
                                "entries": all_review_entries,
                            }

                        yield f"data: {json.dumps(summary)}\n\n"
                        yield f"data: {json.dumps({'kind': 'done', 'summary': summary})}\n\n"

                    except Exception as e:
                        logger.error(f"Analysis stream error: {e}")
                        yield f"data: {json.dumps({'kind': 'error', 'message': str(e)})}\n\n"

                # Return streaming response for orchestrator request
                return StreamingResponse(
                    generate_analysis_with_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                )

            except Exception as e:
                logger.error(f"Comprehensive analysis failed: {e}")
                # Fall through to standard processing

        # Standard request processing
        logger.debug("Starting standard request processing")
        if any(word in msg_lower for word in ["review", "diff", "changes", "git"]):
            logger.debug("Matched review/diff/changes/git")
            progress_tracker.update_status("Analyzing Git repository...")
            progress_tracker.complete_step("Detected Git diff request")
        elif any(word in msg_lower for word in ["explain", "what", "describe"]):
            logger.debug("Matched explain/what/describe")
            progress_tracker.update_status("Scanning codebase...")
            progress_tracker.complete_step("Detected explanation request")
        elif any(word in msg_lower for word in ["fix", "error", "debug", "issue"]):
            logger.debug("Matched fix/error/debug/issue")
            progress_tracker.update_status("Analyzing code issues...")
            progress_tracker.complete_step("Detected debugging request")
        elif (
            any(
                word in msg_lower
                for word in ["create", "implement", "build", "generate", "add", "write"]
            )
            and workspace_root
        ):
            logger.debug(
                "Matched autonomous coding keywords with workspace_root=%s",
                workspace_root,
            )
            progress_tracker.update_status("Preparing autonomous coding...")
            progress_tracker.complete_step("Detected coding request")

            # Check if this is an autonomous coding request
            coding_keywords = [
                "create",
                "implement",
                "build",
                "generate",
                "add",
                "write",
                "make",
                "code",
            ]
            if any(keyword in msg_lower for keyword in coding_keywords):
                logger.debug("Entering autonomous coding block")
                try:
                    # Simple autonomous coding integration
                    reply = f"""I can help you implement that autonomously! 

**🤖 Autonomous Coding Mode Activated**

I'll work like Cline, Copilot, and other AI coding assistants:

1. **Analyze** your request: "{request.message}"
2. **Plan** step-by-step implementation  
3. **Generate** code with your approval
4. **Apply** changes safely to your workspace
5. **Test** and verify the implementation

**Workspace:** `{workspace_root}`

To get started, I need to analyze your codebase and create a detailed implementation plan. Would you like me to proceed?"""

                    actions = [
                        {
                            "type": "startAutonomousTask",
                            "description": "Start autonomous implementation",
                            "workspace_root": workspace_root,
                            "request": request.message,
                        }
                    ]

                    logger.debug("Returning autonomous response")
                    return ChatResponse(
                        content=reply,
                        actions=actions,
                        agentRun={"mode": "autonomous_coding"},
                        reply=reply,
                        should_stream=False,
                        state={"autonomous_coding": True, "workspace": workspace_root},
                        duration_ms=0,
                    )

                except Exception as e:
                    logger.exception("Autonomous coding failed: %s", e)
                    # Fall back to regular agent loop
                    progress_tracker.update_status(
                        "Falling back to standard analysis..."
                    )
            else:
                logger.debug("Coding keywords check failed")
        else:
            logger.debug("No specific patterns matched - default processing")
            progress_tracker.update_status("Analyzing your request...")
            progress_tracker.complete_step("Request type identified")

        logger.debug("Continuing to agent loop")

        # =================================================================
        # IMAGE PROCESSING: Check for image attachments and analyze them
        # This allows NAVI to "see" screenshots and images in the regular
        # (non-streaming) chat endpoint
        # =================================================================
        image_context = ""
        if request.attachments:
            logger.info(
                f"[NAVI-CHAT] Processing {len(request.attachments)} attachments"
            )
            for att in request.attachments:
                att_kind = getattr(att, "kind", None) or (
                    att.get("kind") if isinstance(att, dict) else None
                )
                logger.info(f"[NAVI-CHAT] Attachment kind: {att_kind}")
                if att_kind == "image":
                    att_content = getattr(att, "content", None) or (
                        att.get("content") if isinstance(att, dict) else None
                    )
                    if att_content:
                        try:
                            from backend.services.vision_service import (
                                VisionClient,
                            )

                            # Extract base64 data from data URL
                            if att_content.startswith("data:"):
                                # Format: data:image/png;base64,<data>
                                base64_data = (
                                    att_content.split(",", 1)[1]
                                    if "," in att_content
                                    else att_content
                                )
                            else:
                                base64_data = att_content

                            # Use vision AI to analyze the image
                            # Use the same provider as the user's selected model
                            vision_provider = _get_vision_provider_for_model(
                                request.model
                            )
                            analysis_prompt = f"Analyze this image in detail. The user's question is: {request.message}\n\nProvide a comprehensive analysis including:\n1. What you see in the image\n2. Any text, code, or data visible\n3. UI elements if it's a screenshot\n4. Any errors or issues visible\n5. Relevant information to answer the user's question"

                            logger.info(
                                f"[NAVI-CHAT] Analyzing image with vision provider: {vision_provider}"
                            )
                            vision_response = await VisionClient.analyze_image(
                                image_data=base64_data,
                                prompt=analysis_prompt,
                                provider=vision_provider,
                            )
                            image_context += (
                                f"\n\n=== IMAGE ANALYSIS ===\n{vision_response}\n"
                            )
                            logger.info("[NAVI-CHAT] Image analyzed successfully")
                        except Exception as img_err:
                            logger.warning(
                                f"[NAVI-CHAT] Image analysis failed: {img_err}"
                            )

        # Augment the message with image context if present
        augmented_message = request.message
        if image_context:
            augmented_message = (
                f"{request.message}\n\n[CONTEXT FROM ATTACHED IMAGE(S)]{image_context}"
            )
            logger.info("[NAVI-CHAT] Message augmented with image analysis")

        agent_result = await run_agent_loop(
            user_id=user_id,
            message=augmented_message,  # Use augmented message with image context
            model=_resolve_model(request.model),
            mode=mode,
            db=db,
            attachments=[a.dict() for a in (request.attachments or [])],
            workspace=workspace_data,
        )

        progress_tracker.complete_step("Analysis complete")
        progress_tracker.update_status("Generating response...")

        # Core reply text (may be overridden below)
        reply = str(agent_result.get("reply") or "").strip()
        state: Dict[str, Any] = agent_result.get("state") or {}

        # ------------------------------------------------------------------
        # Repo fast-path enhancement:
        # if the planner marked this as a "which repo" question, derive a
        # real repo name + root path instead of the generic "current" text.
        # ------------------------------------------------------------------
        try:
            if state.get("repo_fast_path") and state.get("kind") in {
                "where",
                "which_repo",
            }:
                repo_root = workspace_root

                # 1) From workspace payload (if any)
                if not repo_root and isinstance(workspace_data, dict):
                    repo_root = workspace_data.get(
                        "workspace_root"
                    ) or workspace_data.get("repo_root")

                # 2) Last resort: backend working directory
                if not repo_root:
                    try:
                        repo_root = os.getcwd()
                    except Exception:  # noqa: BLE001
                        repo_root = None

                repo_name = None
                if repo_root:
                    clean = str(repo_root).rstrip("/\\")
                    base = os.path.basename(clean)
                    repo_name = base or clean

                if not repo_name:
                    repo_name = "current"

                logger.info(
                    "[NAVI-CHAT] Repo debug: workspace_root=%r repo_root=%r repo_name=%r",
                    workspace_root,
                    repo_root,
                    repo_name,
                )

                # Override reply with dynamic repo name
                reply = f"You're currently working in the **{repo_name}** repo."

                # Enrich state so frontends can also use it
                state["repo_name"] = repo_name
                state["repo_root"] = repo_root
                state["repo_fast_path"] = True
                state["kind"] = state.get("kind") or "where"

                agent_result["state"] = state

        except Exception as repo_err:  # noqa: BLE001
            logger.warning(
                "[NAVI-CHAT] Repo fast-path enhancement failed: %s", repo_err
            )

        # Fallback if reply is still empty
        if not reply:
            reply = (
                "I generated an empty response. Could you try asking that again "
                "in a slightly different way?"
            )

        # Planned actions (already shaped in agent_loop)
        actions: List[Dict[str, Any]] = agent_result.get("actions") or []

        # Build a minimal agentRun payload for the Workspace plan card
        agent_run: Optional[Dict[str, Any]] = None
        if actions:
            steps = []
            for idx, step in enumerate(actions):
                if not isinstance(step, dict):
                    try:
                        step = dict(step)
                    except Exception:  # noqa: BLE001
                        step = {"description": str(step)}

                label = (
                    step.get("title")
                    or step.get("description")
                    or step.get("tool")
                    or f"Step {idx + 1}"
                )

                detail_parts = []
                tool_name = step.get("tool")
                if tool_name:
                    detail_parts.append(f"Tool: {tool_name}")

                args = step.get("arguments") or step.get("args")
                if args:
                    detail_parts.append(f"Args: {str(args)[:160]}")

                detail = " | ".join(detail_parts) if detail_parts else ""

                steps.append(
                    {
                        "id": step.get("id") or f"step-{idx + 1}",
                        "label": label,
                        "status": "planned",
                        "detail": detail,
                    }
                )

            agent_run = {
                "duration_ms": agent_result.get("duration_ms"),
                "steps": steps,
            }

        # Extract sources from agent result
        sources = agent_result.get("sources") or []

        # Complete progress tracking
        progress_tracker.complete_step("Response generated")
        progress_tracker.update_status("Ready")

        # NAVI V2: Plan mode - check if approval is required
        requires_approval = state.get("pending_approval", False)
        plan_id = None
        actions_with_risk = []

        if requires_approval and actions:
            # Generate plan ID and format actions with risk assessment
            import uuid

            plan_id = str(uuid.uuid4())

            for action in actions:
                # Determine risk level based on action type
                action_type = action.get("type", "generic")
                tool = action.get("tool", "")

                risk = "low"
                warnings = []

                if action_type == "fileEdit" or tool in [
                    "code.apply_patch",
                    "code.write_file",
                ]:
                    risk = "medium"
                    warnings.append("This will modify files in your workspace")
                elif tool.startswith("pm."):
                    risk = "medium"
                    warnings.append("This will create/modify project management items")
                elif "runCommand" in action_type:
                    risk = "medium"
                    warnings.append("This will execute a command")

                actions_with_risk.append(
                    {
                        "type": action.get("type", "generic"),
                        "path": action.get("filePath"),
                        "command": action.get("command"),
                        "content": action.get("content"),
                        "risk": risk,
                        "warnings": warnings,
                        "preview": action.get("description", ""),
                        "tool": tool,
                        "arguments": action.get("arguments", {}),
                    }
                )

        # Map `reply` -> `content` for the extension
        return ChatResponse(
            content=reply,
            actions=actions,
            agentRun=agent_run,
            sources=sources,  # Pass through sources
            status=progress_tracker.current_status,
            progress_steps=progress_tracker.steps,
            reply=reply,
            should_stream=bool(agent_result.get("should_stream", False)),
            state=state,
            duration_ms=agent_result.get("duration_ms"),
            # NAVI V2: Plan mode fields
            requires_approval=requires_approval,
            plan_id=plan_id,
            actions_with_risk=actions_with_risk,
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("[NAVI-CHAT] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to process NAVI chat",
        )


# ---------------------------------------------------------------------------
# Unified Agent Detection
# ---------------------------------------------------------------------------


def _should_use_unified_agent(message: str) -> bool:
    """
    Detect if a message should use the unified agent (action-oriented requests).

    Returns True for requests that involve taking action rather than just chatting.
    The unified agent uses native LLM tool-use for executing commands, creating files, etc.
    """
    action_patterns = [
        # File/code creation
        r"\b(create|write|make|add|build|generate)\b.*\b(file|component|function|class|test|module|page)\b",
        # Running things - more permissive
        r"\b(run|execute|start|stop|restart|launch)\b.*(project|server|test|build|app|application|script|command)",
        r"\b(run|execute)\s+(the\s+)?(project|tests?|build|server|app)",  # "run the project", "run tests"
        # Bug fixing
        r"\b(fix|debug|repair|resolve|solve)\b.*\b(bug|error|issue|problem|crash|failure)\b",
        # Code editing
        r"\b(edit|modify|update|change|refactor|rename)\b.*\b(file|code|function|variable|class)\b",
        # Package management
        r"\b(install|uninstall|add|remove|upgrade|update)\b.*\b(package|dependency|module|library)\b",
        r"\bnpm\s+(install|run|start|build|test)",  # npm commands
        r"\byarn\s+(install|add|run|start|build|test)",  # yarn commands
        r"\bpip\s+(install|uninstall)",  # pip commands
        r"\bcargo\s+(build|run|test)",  # cargo commands
        r"\bgo\s+(build|run|test|get)",  # go commands
        r"\bpython\s+",  # python scripts
        r"\bnode\s+",  # node scripts
        # Git commands
        r"\bgit\s+(commit|push|pull|merge|rebase|checkout|branch)",
        # Imperative action phrases
        r"^(please\s+)?(can\s+you\s+)?(run|execute|start|create|fix|install|build)",  # "run...", "can you run..."
        # Direct command patterns
        r"^\s*(npm|yarn|pip|cargo|go|python|node|git)\s+",  # Commands at start of message
    ]

    message_lower = message.lower()
    for pattern in action_patterns:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return True

    return False


# ---------------------------------------------------------------------------
# Streaming chat endpoint (SSE)
# ---------------------------------------------------------------------------


@router.post("/chat/stream")
@no_type_check
async def navi_chat_stream(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Streaming version of navi_chat with Server-Sent Events (SSE).

    Returns real-time progress updates and the final response as a stream.
    Used by the VS Code extension for a responsive chat experience.
    """
    from backend.services.streaming_utils import (
        StreamingSession,
        stream_text_with_typing,
    )
    from backend.services.navi_brain import process_navi_request_streaming

    logger.info(
        "[NAVI-STREAM] Starting stream for message: '%s...'",
        request.message[:50] if request.message else "",
    )

    user_id = (request.user_id or "default_user").strip() or "default_user"
    mode = (request.mode or "chat-only").strip() or "chat-only"
    workspace_root = request.workspace_root or (request.workspace or {}).get(
        "workspace_root"
    )

    async def generate_stream():
        """Generator for SSE events."""
        stream_session = StreamingSession()

        try:
            # Emit initial activity
            yield f"data: {json.dumps({'activity': {'kind': 'context', 'label': 'Starting', 'detail': 'Processing your request...', 'status': 'running'}})}\n\n"

            # =================================================================
            # IMAGE PROCESSING: Check for image attachments and analyze them
            # =================================================================
            image_context = ""
            if request.attachments:
                for att in request.attachments:
                    att_kind = getattr(att, "kind", None) or (
                        att.get("kind") if isinstance(att, dict) else None
                    )
                    if att_kind == "image":
                        att_content = getattr(att, "content", None) or (
                            att.get("content") if isinstance(att, dict) else None
                        )
                        if att_content:
                            yield f"data: {json.dumps({'activity': {'kind': 'detection', 'label': 'Analyzing Image', 'detail': 'Processing image with vision AI...', 'status': 'running'}})}\n\n"
                            try:
                                from backend.services.vision_service import (
                                    VisionClient,
                                )

                                # Extract base64 data from data URL
                                if att_content.startswith("data:"):
                                    # Format: data:image/png;base64,<data>
                                    base64_data = (
                                        att_content.split(",", 1)[1]
                                        if "," in att_content
                                        else att_content
                                    )
                                else:
                                    base64_data = att_content

                                # Use vision AI to analyze the image
                                # Use the same provider as the user's selected model
                                vision_provider = _get_vision_provider_for_model(
                                    request.model
                                )
                                analysis_prompt = f"Analyze this image in detail. The user's question is: {request.message}\n\nProvide a comprehensive analysis including:\n1. What you see in the image\n2. Any text, code, or data visible\n3. UI elements if it's a screenshot\n4. Any errors or issues visible\n5. Relevant information to answer the user's question"

                                vision_response = await VisionClient.analyze_image(
                                    image_data=base64_data,
                                    prompt=analysis_prompt,
                                    provider=vision_provider,
                                )
                                image_context += (
                                    f"\n\n=== IMAGE ANALYSIS ===\n{vision_response}\n"
                                )
                                yield f"data: {json.dumps({'activity': {'kind': 'detection', 'label': 'Image Analyzed', 'detail': 'Vision AI analysis complete', 'status': 'done'}})}\n\n"
                            except Exception as img_err:
                                logger.warning(
                                    f"[NAVI-STREAM] Image analysis failed: {img_err}"
                                )
                                yield f"data: {json.dumps({'activity': {'kind': 'detection', 'label': 'Image Analysis', 'detail': 'Could not analyze image', 'status': 'error'}})}\n\n"

            # Augment the message with image context if present
            augmented_message = request.message
            if image_context:
                augmented_message = f"{request.message}\n\n[CONTEXT FROM ATTACHED IMAGE(S)]{image_context}"

            # Check if we have workspace for agent mode
            if not workspace_root:
                # No workspace - use simple chat mode
                logger.info("[NAVI-STREAM] No workspace, using simple chat mode")

                # Call agent loop for response (use augmented_message with image context)
                agent_result = await run_agent_loop(
                    user_id=user_id,
                    message=augmented_message,
                    model=_resolve_model(request.model),
                    mode=mode,
                    db=db,
                    attachments=[a.dict() for a in (request.attachments or [])],
                    workspace=request.workspace or {},
                )

                reply = str(agent_result.get("reply") or "").strip()
                if not reply:
                    reply = "I couldn't generate a response. Please try again."

                # Stream the response content
                async for chunk in stream_text_with_typing(
                    reply,
                    chunk_size=3,
                    delay_ms=12,
                ):
                    content_event = stream_session.content(chunk)
                    yield f"data: {json.dumps(content_event)}\n\n"

                # Include actions if any
                actions = agent_result.get("actions") or []
                if actions:
                    yield f"data: {json.dumps({'actions': actions})}\n\n"

                yield f"data: {json.dumps({'router_info': {'mode': mode, 'model': request.model}})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # =================================================================
            # UNIFIED AGENT: Check if this is an action-oriented request
            # =================================================================
            if _should_use_unified_agent(request.message):
                logger.info(
                    "[NAVI-STREAM] 🚀 Routing to Unified Agent for action request: '%s...'",
                    request.message[:50],
                )
                from backend.services.unified_agent import UnifiedAgent, AgentEventType

                # For unified agent, prefer OpenAI as it has more reliable tool-use
                # Fall back to DEFAULT_LLM_PROVIDER if OpenAI key not available
                provider = request.provider or "openai"
                # Let unified agent select the appropriate model for the provider
                # Don't use _resolve_model as it may return a model incompatible with provider
                model_name = None  # UnifiedAgent will use its default for the provider

                # Build project context
                project_context = None
                if request.attachments:
                    for att in request.attachments:
                        att_path = getattr(att, "path", None) or (
                            att.get("path") if isinstance(att, dict) else None
                        )
                        if att_path:
                            project_context = {"current_file": att_path}
                            break

                # Build conversation history
                conv_history = None
                if request.conversation_history:
                    conv_history = [
                        {
                            "role": msg.get("type", msg.get("role", "user")),
                            "content": msg.get("content", ""),
                        }
                        for msg in request.conversation_history
                        if msg.get("content")
                    ]

                # Emit unified agent start event
                yield f"data: {json.dumps({'router_info': {'provider': provider, 'model': model_name or 'auto', 'mode': 'unified_agent', 'task_type': 'action'}})}\n\n"
                yield f"data: {json.dumps({'activity': {'kind': 'agent_start', 'label': 'Agent', 'detail': 'Starting unified agent with native tool-use...', 'status': 'running'}})}\n\n"

                try:
                    agent = UnifiedAgent(
                        provider=provider,
                        model=model_name,
                    )

                    async for event in agent.run(
                        message=augmented_message,
                        workspace_path=workspace_root,
                        conversation_history=conv_history,
                        project_context=project_context,
                    ):
                        # Convert agent events to SSE format
                        if event.type == AgentEventType.THINKING:
                            yield f"data: {json.dumps({'activity': {'kind': 'thinking', 'label': 'Thinking', 'detail': event.data.get('message', ''), 'status': 'running'}})}\n\n"

                        elif event.type == AgentEventType.TEXT:
                            yield f"data: {json.dumps({'content': event.data})}\n\n"

                        elif event.type == AgentEventType.TOOL_CALL:
                            tool_name = event.data.get("name", "unknown")
                            tool_args = event.data.get("arguments", {})

                            kind = "command"
                            label = tool_name
                            detail = ""
                            purpose = None  # Command context: why running this

                            if tool_name == "read_file":
                                kind = "read"
                                label = "Reading"
                                detail = tool_args.get("path", "")
                            elif tool_name == "write_file":
                                kind = "create"
                                label = "Creating"
                                detail = tool_args.get("path", "")
                            elif tool_name == "edit_file":
                                kind = "edit"
                                label = "Editing"
                                detail = tool_args.get("path", "")
                            elif tool_name == "run_command":
                                kind = "command"
                                label = "Running"
                                cmd = tool_args.get("command", "")
                                detail = cmd
                                # Generate purpose based on command pattern (Bug 5 fix)
                                cmd_lower = cmd.lower()
                                if (
                                    "npm install" in cmd_lower
                                    or "pip install" in cmd_lower
                                    or "yarn add" in cmd_lower
                                ):
                                    purpose = "Installing dependencies to ensure all required packages are available"
                                elif (
                                    "npm run dev" in cmd_lower
                                    or "npm start" in cmd_lower
                                ):
                                    purpose = "Starting the development server to run the application"
                                elif (
                                    "npm run build" in cmd_lower
                                    or "npm run compile" in cmd_lower
                                ):
                                    purpose = "Building the project to compile and bundle the code"
                                elif (
                                    "npm test" in cmd_lower
                                    or "pytest" in cmd_lower
                                    or "jest" in cmd_lower
                                ):
                                    purpose = "Running tests to verify the code is working correctly"
                                elif "git " in cmd_lower:
                                    purpose = (
                                        "Running git command to manage version control"
                                    )
                                elif (
                                    "lsof" in cmd_lower
                                    or "netstat" in cmd_lower
                                    or "ps " in cmd_lower
                                ):
                                    purpose = "Checking system processes and port usage"
                                elif "kill" in cmd_lower or "pkill" in cmd_lower:
                                    purpose = "Stopping a running process"
                                elif "curl" in cmd_lower or "wget" in cmd_lower:
                                    purpose = "Making an HTTP request to check connectivity or fetch data"
                                elif "mkdir" in cmd_lower:
                                    purpose = (
                                        "Creating a directory for the project structure"
                                    )
                                elif "rm " in cmd_lower or "rm -" in cmd_lower:
                                    purpose = (
                                        "Removing files or directories to clean up"
                                    )
                                elif (
                                    "cat " in cmd_lower
                                    or "head " in cmd_lower
                                    or "tail " in cmd_lower
                                ):
                                    purpose = "Reading file contents for inspection"
                                elif "grep" in cmd_lower:
                                    purpose = "Searching for patterns in files"
                            elif tool_name == "search_files":
                                kind = "search"
                                label = "Searching"
                                detail = tool_args.get("pattern", "")
                            elif tool_name == "list_directory":
                                kind = "read"
                                label = "Listing"
                                detail = tool_args.get("path", "")

                            activity_data = {
                                "kind": kind,
                                "label": label,
                                "detail": detail,
                                "status": "running",
                            }
                            if purpose:
                                activity_data["purpose"] = purpose
                            yield f"data: {json.dumps({'activity': activity_data})}\n\n"

                        elif event.type == AgentEventType.TOOL_RESULT:
                            # event.data = {"id": ..., "name": ..., "result": {...}}
                            tool_result = event.data.get("result", {})
                            success = tool_result.get("success", False)
                            status = "done" if success else "error"
                            # Get meaningful output preview
                            output_preview = (
                                tool_result.get("message", "")
                                or tool_result.get("content", "")[:200]
                                if tool_result.get("content")
                                else (
                                    tool_result.get("error", "")
                                    or str(tool_result.get("items", [])[:3])
                                    if tool_result.get("items")
                                    else ""
                                )
                            )
                            yield f"data: {json.dumps({'activity': {'kind': 'tool_result', 'label': 'Result', 'detail': output_preview[:200], 'status': status}})}\n\n"

                        elif event.type == AgentEventType.VERIFICATION:
                            yield f"data: {json.dumps({'verification': event.data})}\n\n"

                        elif event.type == AgentEventType.FIXING:
                            yield f"data: {json.dumps({'activity': {'kind': 'fixing', 'label': 'Fixing', 'detail': event.data.get('message', ''), 'status': 'running'}})}\n\n"

                        elif event.type == AgentEventType.DONE:
                            yield f"data: {json.dumps({'activity': {'kind': 'done', 'label': 'Complete', 'detail': event.data.get('summary', 'Task completed'), 'status': 'done'}})}\n\n"
                            yield f"data: {json.dumps({'done': True, 'summary': event.data})}\n\n"

                        elif event.type == AgentEventType.ERROR:
                            yield f"data: {json.dumps({'error': event.data.get('message', 'Unknown error')})}\n\n"

                except Exception as e:
                    logger.exception("[NAVI Unified Agent] Error: %s", e)
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

                yield "data: [DONE]\n\n"
                return

            # =================================================================
            # NAVI BRAIN: For analysis, explanation, and conversation requests
            # =================================================================
            logger.info(
                "[NAVI-STREAM] Using NAVI brain streaming for workspace: %s",
                workspace_root,
            )

            # Extract context from request
            current_file = None
            current_file_content = None
            selection = None
            errors = None

            # Check attachments for file content
            if request.attachments:
                for att in request.attachments:
                    att_kind = getattr(att, "kind", None) or (
                        att.get("kind") if isinstance(att, dict) else None
                    )
                    att_content = getattr(att, "content", None) or (
                        att.get("content") if isinstance(att, dict) else None
                    )
                    att_path = getattr(att, "path", None) or (
                        att.get("path") if isinstance(att, dict) else None
                    )

                    if att_kind in ("file", "code") and att_content:
                        if not current_file:
                            current_file = att_path
                        if not current_file_content:
                            current_file_content = att_content
                        break

            # Determine auto-execute mode
            auto_execute = mode in (
                "agent-full-access",
                "agent_full_access",
                "full-access",
                "full_access",
            )

            # Show current file context if available
            if current_file:
                yield f"data: {json.dumps({'activity': {'kind': 'context', 'label': 'Active file', 'detail': current_file, 'status': 'done'}})}\n\n"

            # Stream from NAVI brain
            navi_result = None
            files_read_live = []

            # Build conversation history for context
            conversation_history_for_llm = None
            if request.conversation_history:
                # Convert frontend format to LLM format
                conversation_history_for_llm = [
                    {
                        "role": msg.get("type", msg.get("role", "user")),
                        "content": msg.get("content", ""),
                    }
                    for msg in request.conversation_history
                    if msg.get("content")
                ]
                logger.info(
                    "[NAVI-STREAM] Using conversation history with %d messages",
                    len(conversation_history_for_llm),
                )

            async for event in process_navi_request_streaming(
                message=request.message,
                workspace_path=workspace_root,
                llm_provider=request.provider or "openai",
                llm_model=_resolve_model(request.model),
                api_key=None,
                current_file=current_file,
                current_file_content=current_file_content,
                selection=selection,
                open_files=None,
                errors=errors,
                conversation_history=conversation_history_for_llm,
            ):
                # Stream activity events
                if "activity" in event:
                    activity = event["activity"]
                    if activity.get("kind") == "file_read":
                        files_read_live.append(activity.get("detail", ""))
                    yield f"data: {json.dumps({'activity': activity})}\n\n"

                # Stream narrative events (conversational explanations like Claude Code)
                elif "narrative" in event:
                    narrative_text = event["narrative"]
                    yield f"data: {json.dumps({'narrative': narrative_text})}\n\n"

                # Stream thinking content
                elif "thinking" in event:
                    thinking_text = event["thinking"]
                    yield f"data: {json.dumps({'thinking': thinking_text})}\n\n"

                # Capture final result
                elif "result" in event:
                    navi_result = event["result"]

            # Process final result
            if navi_result:
                logger.info("[NAVI-STREAM] Result keys: %s", list(navi_result.keys()))

                # Emit activity for files to create/modify
                files_created = navi_result.get("files_created", [])
                files_modified = navi_result.get("files_modified", [])
                file_edits = navi_result.get("file_edits", [])

                for file_path in files_created:
                    yield f"data: {json.dumps({'activity': {'kind': 'create', 'label': 'Creating', 'detail': file_path, 'status': 'done'}})}\n\n"

                for file_path in files_modified:
                    yield f"data: {json.dumps({'activity': {'kind': 'edit', 'label': 'Editing', 'detail': file_path, 'status': 'done'}})}\n\n"

                # Build and stream response content
                response_content = navi_result.get(
                    "message", "Task completed successfully."
                )

                async for chunk in stream_text_with_typing(
                    response_content,
                    chunk_size=3,
                    delay_ms=12,
                ):
                    content_event = stream_session.content(chunk)
                    yield f"data: {json.dumps(content_event)}\n\n"

                # Build actions from result
                actions = []
                proposed_actions = navi_result.get("actions", [])
                for action in proposed_actions:
                    actions.append(action)

                for edit in file_edits:
                    file_path_value = edit.get("filePath") or edit.get("path")
                    if file_path_value:
                        actions.append(
                            {
                                "type": edit.get("type", "editFile"),
                                "filePath": file_path_value,
                                "content": edit.get("content"),
                                "diff": edit.get("diff"),
                                "additions": edit.get("additions"),
                                "deletions": edit.get("deletions"),
                            }
                        )

                # Add files_created that aren't in file_edits
                existing_paths = {
                    a.get("filePath") for a in actions if a.get("filePath")
                }
                for file_path in files_created:
                    if file_path not in existing_paths:
                        content = None
                        for edit in file_edits:
                            edit_path = edit.get("filePath") or edit.get("path")
                            if edit_path == file_path:
                                content = edit.get("content")
                                break
                        if content:
                            actions.append(
                                {
                                    "type": "createFile",
                                    "filePath": file_path,
                                    "content": content,
                                }
                            )

                if actions:
                    logger.info(
                        "[NAVI-STREAM] Sending %d actions: %s",
                        len(actions),
                        [a.get("type") for a in actions],
                    )
                    yield f"data: {json.dumps({'actions': actions})}\n\n"

                # Include next_steps if available
                next_steps = navi_result.get("next_steps", [])
                if next_steps:
                    yield f"data: {json.dumps({'type': 'navi.next_steps', 'next_steps': next_steps})}\n\n"

                # Persist conversation to database (non-blocking, failure won't break stream)
                try:
                    if request.conversation_id:
                        from uuid import UUID

                        memory_service = ConversationMemoryService(db)
                        conv_uuid = UUID(request.conversation_id)

                        # Check if conversation exists, create if not
                        existing_conv = memory_service.get_conversation(conv_uuid)
                        if not existing_conv:
                            # Create new conversation with this ID
                            # Note: This requires user_id as int, but we have string
                            # For now, we'll use a hash of the user_id string
                            user_id_int = abs(hash(user_id)) % (10**9)
                            memory_service.db.execute(
                                text(
                                    """
                                    INSERT INTO conversations (id, user_id, workspace_path, status, created_at, updated_at)
                                    VALUES (:id, :user_id, :workspace_path, 'active', NOW(), NOW())
                                    ON CONFLICT (id) DO NOTHING
                                """
                                ),
                                {
                                    "id": str(conv_uuid),
                                    "user_id": user_id_int,
                                    "workspace_path": workspace_root,
                                },
                            )
                            memory_service.db.commit()
                            logger.info(
                                "[NAVI-STREAM] Created conversation %s", conv_uuid
                            )

                        # Store user message
                        await memory_service.add_message(
                            conversation_id=conv_uuid,
                            role="user",
                            content=request.message,
                            metadata={"workspace": workspace_root},
                            generate_embedding=False,  # Skip embedding for speed
                        )

                        # Store assistant response
                        await memory_service.add_message(
                            conversation_id=conv_uuid,
                            role="assistant",
                            content=response_content,
                            generate_embedding=False,  # Skip embedding for speed
                        )
                        logger.info(
                            "[NAVI-STREAM] Persisted conversation %s with %d char response",
                            conv_uuid,
                            len(response_content),
                        )
                except Exception as mem_error:
                    # Don't fail the stream if memory persistence fails
                    logger.warning(
                        "[NAVI-STREAM] Failed to persist conversation: %s",
                        mem_error,
                    )

            # Include router info
            yield f"data: {json.dumps({'router_info': {'provider': request.provider or 'openai', 'model': request.model, 'mode': mode, 'auto_execute': auto_execute}})}\n\n"

            # Include streaming metrics
            metrics = stream_session.get_metrics()
            yield f"data: {json.dumps(metrics)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("[NAVI-STREAM] Streaming error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            metrics = stream_session.get_metrics()
            yield f"data: {json.dumps(metrics)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _apply_auto_fix_by_id(
    content: str, fix_id: str, file_path: str, context: Dict[str, Any]
) -> Tuple[str, bool, str]:
    """
    Apply auto-fix by ID implementation.

    Args:
        content: File content to fix
        fix_id: ID of the fix to apply
        file_path: Path to the file being fixed
        context: Additional context

    Returns:
        Tuple of (modified_content, success, description)
    """
    try:
        # Simple implementation for common fixes
        if fix_id == "add_import":
            # Add missing import
            if "import" not in content[:100]:
                modified_content = f"import os\nimport sys\n\n{content}"
                return modified_content, True, "Added missing imports"

        elif fix_id == "fix_syntax":
            # Fix common syntax issues
            modified_content = content.replace("=None", " = None")
            modified_content = modified_content.replace("!=None", " is not None")
            modified_content = modified_content.replace("==None", " is None")
            if modified_content != content:
                return modified_content, True, "Fixed syntax issues"

        elif fix_id == "add_type_hints":
            # Add basic type hints
            if "from typing import" not in content:
                modified_content = (
                    f"from typing import Optional, List, Dict, Any\n\n{content}"
                )
                return modified_content, True, "Added type import"

        return content, False, f"No implementation for fix_id: {fix_id}"

    except Exception as e:
        return content, False, f"Fix failed: {str(e)}"


# ============================================================================
# NAVI V2: Tool-Use Streaming Endpoint (Claude Code Style)
# ============================================================================


class ToolStreamRequest(BaseModel):
    """Request for tool-use streaming endpoint."""

    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    workspace_path: Optional[str] = None
    workspace_root: Optional[str] = None  # Alias for workspace_path from extension
    current_file: Optional[str] = None
    project_type: Optional[str] = None
    # Fields from extension that we accept but may not use directly
    mode: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    selection: Optional[str] = None
    current_file_content: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None
    state: Optional[Dict[str, Any]] = None
    last_action_error: Optional[Dict[str, Any]] = None


def _parse_model_string(model_str: Optional[str]) -> Tuple[str, str]:
    """
    Parse model string like 'openai/gpt-4o' into (provider, model).
    Returns ('openai', 'gpt-4o') for default.
    """
    if not model_str:
        return "openai", "gpt-4o"

    if "/" in model_str:
        parts = model_str.split("/", 1)
        provider = parts[0].lower()
        model = parts[1]
        # Normalize provider names
        if provider in ("openai", "gpt"):
            return "openai", model
        elif provider in ("anthropic", "claude"):
            return "anthropic", model
        elif provider in ("groq",):
            return "groq", model
        elif provider in ("openrouter",):
            return "openrouter", model
        else:
            return provider, model
    else:
        # Just a model name, assume OpenAI
        return "openai", model_str


@router.post("/chat/stream/v2")
async def navi_chat_stream_v2(
    request: ToolStreamRequest,
    http_request: Request,
):
    """
    NAVI V2 Chat Stream - Claude Code Style

    This endpoint uses tool-use/function-calling to provide a conversational
    experience where the LLM:
    1. Explains what it's doing in natural language
    2. Calls tools (read_file, edit_file, run_command) inline
    3. Continues explaining based on results

    The stream interleaves:
    - text: Narrative text from the LLM
    - tool_call: When the LLM wants to use a tool
    - tool_result: Results from tool execution
    - done: When complete
    """
    import os
    from backend.services.streaming_agent import (
        stream_with_tools_anthropic,
        stream_with_tools_openai,
    )

    # Determine workspace path (accept both workspace_path and workspace_root from extension)
    workspace_path = request.workspace_path or request.workspace_root
    if not workspace_path:
        workspace_path = os.environ.get("AEP_WORKSPACE_PATH", os.getcwd())

    # Build context
    context = {}
    if request.current_file:
        context["current_file"] = request.current_file
    if request.project_type:
        context["project_type"] = request.project_type

    # Parse the model string (handles "openai/gpt-4o" format from extension)
    provider, model_name = _parse_model_string(request.model)

    # Override with explicit provider if given
    if request.provider:
        provider = request.provider

    logger.info(f"[NAVI V2] Parsed model: provider={provider}, model={model_name}")

    async def stream_generator():
        """Generate SSE events from the streaming agent."""
        import asyncio
        from backend.services.navi_brain import ProjectAnalyzer
        from backend.services.narrative_generator import NarrativeGenerator
        from backend.agent.intent_classifier import classify_intent
        from backend.agent.intent_schema import IntentKind

        try:
            # PHASE 0: Intent Classification (determines what analysis to do)
            # This is key to being DYNAMIC - we don't do heavy analysis for simple greetings
            intent = classify_intent(request.message)

            logger.info(
                f"[NAVI V2] Classified intent: family={intent.family.value}, kind={intent.kind.value}, confidence={intent.confidence}"
            )

            # Emit intent detection activity
            intent_activity = {
                "type": "activity",
                "activity": {
                    "kind": "intent",
                    "label": "Understanding request",
                    "detail": f"Detected: {intent.kind.value} ({int(intent.confidence * 100)}%)",
                    "status": "done",
                },
            }
            yield f"data: {json.dumps(intent_activity)}\n\n"

            # Also emit the intent for frontend to use
            intent_event = {
                "type": "intent",
                "intent": {
                    "family": intent.family.value,
                    "kind": intent.kind.value,
                    "confidence": intent.confidence,
                },
            }
            yield f"data: {json.dumps(intent_event)}\n\n"

            # Determine if we need project analysis based on intent
            # Skip heavy analysis for simple greetings and unknown intents
            intents_needing_analysis = {
                IntentKind.INSPECT_REPO,
                IntentKind.SUMMARIZE_FILE,
                IntentKind.SEARCH_CODE,
                IntentKind.MODIFY_CODE,
                IntentKind.CREATE_FILE,
                IntentKind.REFACTOR_CODE,
                IntentKind.IMPLEMENT_FEATURE,
                IntentKind.FIX_BUG,
                IntentKind.FIX_DIAGNOSTICS,
                IntentKind.RUN_TESTS,
                IntentKind.GENERATE_TESTS,
                IntentKind.RUN_LINT,
                IntentKind.RUN_BUILD,
                IntentKind.EXPLAIN_CODE,
                IntentKind.EXPLAIN_ERROR,
                IntentKind.ARCHITECTURE_OVERVIEW,
                IntentKind.DESIGN_PROPOSAL,
                IntentKind.IMPLEMENT,
                IntentKind.FIX,
                IntentKind.CREATE,
            }

            needs_project_analysis = intent.kind in intents_needing_analysis

            # Build context - start with basic context
            enhanced_context = context.copy() if context else {}
            source_files = {}
            project_info = None

            # PHASE 1: Project Analysis (ONLY if needed based on intent)
            if needs_project_analysis:
                # Emit project detection activity
                yield f"data: {json.dumps({'type': 'activity', 'activity': {'kind': 'detection', 'label': 'Detecting project', 'detail': 'Analyzing workspace...', 'status': 'running'}})}\n\n"

                # Run project analysis
                project_info = ProjectAnalyzer.analyze(workspace_path)

                yield f"data: {json.dumps({'type': 'activity', 'activity': {'kind': 'detection', 'label': 'Detected', 'detail': project_info.framework or project_info.project_type, 'status': 'done'}})}\n\n"

                # PHASE 2: Read source files with streaming activities (like Copilot)
                file_count = ProjectAnalyzer.get_important_files_count(workspace_path)

                # Stream file reads one by one for real-time activity display
                async for event in ProjectAnalyzer.analyze_source_files_streaming(
                    workspace_path, max_files=file_count
                ):
                    if "activity" in event:
                        # Emit file read activity to frontend
                        activity_data = {
                            "type": "activity",
                            "activity": event["activity"],
                        }
                        yield f"data: {json.dumps(activity_data)}\n\n"
                        await asyncio.sleep(0.02)  # Small delay for UI to update
                    elif "files" in event:
                        source_files = event["files"]

                # Emit narrative about what we found
                # Note: Don't emit file count here - it will be tracked dynamically by frontend
                # The LLM may read additional files via tool calls, so count would be misleading
                if source_files:
                    narrative = NarrativeGenerator.for_project_detection(
                        {
                            "project_type": project_info.project_type,
                            "framework": project_info.framework,
                            "dependencies": project_info.dependencies,
                        }
                    )
                    # Don't include file count - let frontend track total from activities
                    narrative_data = {"type": "narrative", "content": narrative}
                    yield f"data: {json.dumps(narrative_data)}\n\n"

                # Add project context
                enhanced_context["project_type"] = project_info.project_type
                enhanced_context["framework"] = project_info.framework
                enhanced_context["files_analyzed"] = list(source_files.keys())

                # Add source file contents to context (for DETAILED responses)
                # Include more files and more content per file for comprehensive analysis
                if source_files:
                    files_summary = []
                    # Prioritize important files: package.json, configs, main entry points
                    priority_patterns = [
                        "package.json",
                        "tsconfig",
                        "next.config",
                        "index.",
                        "_app.",
                        "main.",
                    ]
                    sorted_files = sorted(
                        source_files.items(),
                        key=lambda x: (
                            (
                                0
                                if any(p in x[0].lower() for p in priority_patterns)
                                else 1
                            ),
                            x[0],
                        ),
                    )
                    for path, content in sorted_files[:10]:  # Top 10 files
                        files_summary.append(
                            f"--- {path} ---\n{content[:3000]}"
                        )  # More content per file
                    enhanced_context["source_files_preview"] = "\n\n".join(
                        files_summary
                    )
            else:
                # For simple intents like GREET, just log and continue without analysis
                logger.info(
                    f"[NAVI V2] Skipping project analysis for intent: {intent.kind.value}"
                )

            # Add intent info to context for LLM
            enhanced_context["detected_intent"] = {
                "family": intent.family.value,
                "kind": intent.kind.value,
                "confidence": intent.confidence,
            }

            # PHASE 3: Stream LLM response with tools
            yield f"data: {json.dumps({'type': 'activity', 'activity': {'kind': 'llm_call', 'label': 'Generating response', 'detail': 'Thinking...', 'status': 'running'}})}\n\n"

            if provider == "anthropic":
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                # Use a valid Claude model
                if not model_name or "gpt" in model_name.lower():
                    model_name_use = "claude-sonnet-4-20250514"
                else:
                    model_name_use = model_name

                async for event in stream_with_tools_anthropic(
                    message=request.message,
                    workspace_path=workspace_path,
                    api_key=api_key,
                    model=model_name_use,
                    context=enhanced_context,  # Use enhanced context with file info
                    conversation_history=request.conversation_history,  # Pass conversation history for context
                    conversation_id=request.conversation_id,  # Pass session ID for memory tracking
                ):
                    yield f"data: {json.dumps(event.to_dict())}\n\n"

            else:  # OpenAI or compatible
                api_key = os.environ.get("OPENAI_API_KEY", "")
                model_name_use = model_name or "gpt-4o"

                # Handle OpenRouter, Groq, etc.
                base_url = "https://api.openai.com/v1"
                if provider == "openrouter":
                    api_key = os.environ.get("OPENROUTER_API_KEY", "")
                    base_url = "https://openrouter.ai/api/v1"
                elif provider == "groq":
                    api_key = os.environ.get("GROQ_API_KEY", "")
                    base_url = "https://api.groq.com/openai/v1"

                async for event in stream_with_tools_openai(
                    message=request.message,
                    workspace_path=workspace_path,
                    api_key=api_key,
                    model=model_name_use,
                    base_url=base_url,
                    context=enhanced_context,  # Use enhanced context with file info
                    conversation_history=request.conversation_history,  # Pass conversation history for context
                ):
                    yield f"data: {json.dumps(event.to_dict())}\n\n"

            # Mark LLM activity as done
            yield f"data: {json.dumps({'type': 'activity', 'activity': {'kind': 'llm_call', 'label': 'Generating response', 'detail': 'Complete', 'status': 'done'}})}\n\n"

        except Exception as e:
            logger.exception(f"[NAVI V2] Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# NAVI V3: Autonomous Agent Endpoint (End-to-End Task Completion)
# ============================================================================


class AutonomousTaskRequest(BaseModel):
    """Request for autonomous task execution.

    Accepts both workspace_path (direct) and workspace_root (from VS Code extension).
    Also handles model ID mapping for different providers.
    """

    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    workspace_path: Optional[str] = None
    workspace_root: Optional[str] = None  # Alias from VS Code extension
    run_verification: bool = True
    max_iterations: int = 5
    # Additional fields from VS Code extension
    conversation_history: Optional[list] = None
    attachments: Optional[list] = None  # Support image/file attachments
    conversation_id: Optional[str] = None
    mode: Optional[str] = None
    user_id: Optional[str] = None
    attachments: Optional[list] = None
    current_file: Optional[str] = None
    current_file_content: Optional[str] = None
    selection: Optional[str] = None
    errors: Optional[list] = None
    state: Optional[dict] = None
    last_action_error: Optional[dict] = None


def _map_model_to_provider(model: Optional[str]) -> tuple[str, str]:
    """
    Map a model ID to the correct provider and model name.

    Handles formats like:
    - "gpt-4o" -> ("openai", "gpt-4o")
    - "openai/gpt-4o" -> ("openai", "gpt-4o")
    - "anthropic/claude-3-sonnet" -> ("anthropic", "claude-sonnet-4-20250514")
    - "gpt-5.1" -> ("openai", "gpt-4o")  # unknown models default to gpt-4o

    Returns (provider, model_id) tuple.
    """
    if not model:
        return "openai", "gpt-4o"

    # Handle provider/model format (e.g., "openai/gpt-4o")
    if "/" in model:
        parts = model.split("/", 1)
        provider_hint = parts[0].lower()
        model_name = parts[1]
    else:
        provider_hint = ""
        model_name = model

    model_lower = model_name.lower()

    # OpenAI models
    if provider_hint == "openai" or any(
        x in model_lower for x in ["gpt-4", "gpt-3", "o1-", "o3-", "davinci", "curie"]
    ):
        # Validate model name - only return known OpenAI models
        valid_openai = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
            "o3-mini",
        ]
        if model_name in valid_openai:
            return "openai", model_name
        # Default to gpt-4o for unknown OpenAI models
        return "openai", "gpt-4o"

    # Anthropic models
    if provider_hint == "anthropic" or any(x in model_lower for x in ["claude"]):
        # Normalize claude model names to current versions
        if "sonnet" in model_lower:
            return "anthropic", "claude-sonnet-4-20250514"
        elif "opus" in model_lower:
            return "anthropic", "claude-opus-4-20250514"
        elif "haiku" in model_lower:
            return "anthropic", "claude-3-5-haiku-20241022"
        return "anthropic", "claude-sonnet-4-20250514"  # Default to sonnet

    # Groq models
    if provider_hint == "groq" or any(x in model_lower for x in ["llama", "mixtral"]):
        return "groq", model_name

    # Google models
    if provider_hint == "google" or any(x in model_lower for x in ["gemini", "palm"]):
        return "google", model_name

    # Default to OpenAI with gpt-4o for unknown models
    return "openai", "gpt-4o"


def _get_vision_provider_for_model(model: Optional[str]):
    """
    Get the appropriate VisionProvider for the user's selected model.

    Maps the chat model provider to the corresponding vision provider:
    - OpenAI models -> VisionProvider.OPENAI (GPT-4 Vision)
    - Anthropic models -> VisionProvider.ANTHROPIC (Claude Vision)
    - Google models -> VisionProvider.GOOGLE (Gemini Vision)
    - Others -> Default to ANTHROPIC (Claude has strong vision capabilities)
    """
    from backend.services.vision_service import VisionProvider

    if not model:
        return VisionProvider.ANTHROPIC  # Default to Claude

    provider, _ = _map_model_to_provider(model)

    if provider == "openai":
        return VisionProvider.OPENAI
    elif provider == "anthropic":
        return VisionProvider.ANTHROPIC
    elif provider == "google":
        return VisionProvider.GOOGLE
    else:
        # Groq and other providers don't have vision - fall back to Claude
        return VisionProvider.ANTHROPIC


@router.post("/chat/autonomous")
async def navi_autonomous_task(
    request: AutonomousTaskRequest,
    http_request: Request,
):
    # DEBUG: Print to stdout to ensure this endpoint is being called
    print("[NAVI Autonomous DEBUG] ========== ENDPOINT CALLED ==========")
    print(
        f"[NAVI Autonomous DEBUG] Message: {request.message[:100] if request.message else 'None'}..."
    )
    print(f"[NAVI Autonomous DEBUG] Attachments: {request.attachments}")
    print("[NAVI Autonomous DEBUG] =====================================")
    """
    NAVI Autonomous Task Execution

    This endpoint executes tasks end-to-end with:
    1. Automatic verification (type checking, tests, builds)
    2. Self-healing on errors (analyze failures, fix, retry)
    3. Iteration until success or max attempts

    The stream includes:
    - status: Current phase (planning, executing, verifying, fixing, completed, failed)
    - text: Narrative explanation from the LLM
    - tool_call: Tool being called
    - tool_result: Result of tool execution
    - verification: Results of verification commands
    - iteration: Current iteration info
    - complete: Final summary

    Example use cases:
    - "Add a login form component with validation and tests"
    - "Fix the type errors in the user service"
    - "Refactor the API routes to use async/await"
    """
    import os
    from backend.services.autonomous_agent import AutonomousAgent

    # Determine workspace path (support both workspace_path and workspace_root)
    workspace_path = request.workspace_path or request.workspace_root
    if not workspace_path:
        workspace_path = os.environ.get("AEP_WORKSPACE_PATH", os.getcwd())

    # Map model to provider
    if request.provider:
        provider = request.provider
        model = request.model
    else:
        provider, model = _map_model_to_provider(request.model)

    logger.info(
        f"[NAVI Autonomous] Provider: {provider}, Model: {model}, Workspace: {workspace_path}"
    )

    # Get API key based on provider
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    elif provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
    elif provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY", "")
    elif provider == "google":
        api_key = os.environ.get("GOOGLE_API_KEY", "")
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")

    # Process image attachments if present
    augmented_message = request.message
    logger.info(
        f"[NAVI Autonomous] Checking attachments: {request.attachments is not None}, count: {len(request.attachments) if request.attachments else 0}"
    )
    if request.attachments:
        logger.info(
            f"[NAVI Autonomous] Processing {len(request.attachments)} attachments"
        )
        image_context = ""
        for att in request.attachments:
            logger.info(
                f"[NAVI Autonomous] Attachment: {type(att)}, keys: {att.keys() if isinstance(att, dict) else 'N/A'}"
            )
            att_kind = (
                att.get("kind") if isinstance(att, dict) else getattr(att, "kind", None)
            )
            logger.info(f"[NAVI Autonomous] Attachment kind: {att_kind}")
            if att_kind == "image":
                att_content = (
                    att.get("content")
                    if isinstance(att, dict)
                    else getattr(att, "content", None)
                )
                if att_content:
                    try:
                        from backend.services.vision_service import (
                            VisionClient,
                        )

                        # Extract base64 data from data URL
                        if att_content.startswith("data:"):
                            base64_data = (
                                att_content.split(",", 1)[1]
                                if "," in att_content
                                else att_content
                            )
                        else:
                            base64_data = att_content

                        # Use vision AI to analyze the image
                        # Use the same provider as the user's selected model
                        vision_provider = _get_vision_provider_for_model(request.model)
                        analysis_prompt = f"Analyze this image in detail. The user's question is: {request.message}\n\nProvide a comprehensive analysis including:\n1. What you see in the image\n2. Any text, code, or data visible\n3. UI elements if it's a screenshot\n4. Any errors or issues visible\n5. Relevant information to answer the user's question"

                        vision_response = await VisionClient.analyze_image(
                            image_data=base64_data,
                            prompt=analysis_prompt,
                            provider=vision_provider,
                        )
                        image_context += (
                            f"\n\n=== IMAGE ANALYSIS ===\n{vision_response}\n"
                        )
                        logger.info("[NAVI Autonomous] Image analyzed successfully")
                    except Exception as img_err:
                        logger.warning(
                            f"[NAVI Autonomous] Image analysis failed: {img_err}"
                        )

        if image_context:
            augmented_message = (
                f"{request.message}\n\n[CONTEXT FROM ATTACHED IMAGE(S)]{image_context}"
            )
            logger.info("[NAVI Autonomous] Message augmented with image analysis")

    async def stream_generator():
        """Generate SSE events from the autonomous agent with heartbeat to prevent timeout."""
        import asyncio

        async def heartbeat_wrapper(agent_generator):
            """Wrap agent generator with periodic heartbeat events to keep SSE connection alive."""
            last_event_time = time.time()
            heartbeat_interval = 15  # Send heartbeat every 15 seconds of silence

            async def send_heartbeat():
                """Send periodic heartbeat events."""
                while True:
                    await asyncio.sleep(heartbeat_interval)
                    current_time = time.time()
                    if current_time - last_event_time >= heartbeat_interval:
                        yield {
                            "type": "heartbeat",
                            "timestamp": time.time() * 1000,
                            "message": "Connection alive"
                        }

            # Create heartbeat task
            heartbeat_task = asyncio.create_task(
                asyncio.sleep(0)  # Placeholder, we'll send heartbeats manually
            )

            try:
                # Process events from agent with heartbeat injection
                pending_tasks = set()
                agent_task = asyncio.create_task(agent_generator.__anext__())

                while True:
                    # Wait for either agent event or heartbeat timeout
                    done, pending = await asyncio.wait(
                        {agent_task},
                        timeout=heartbeat_interval
                    )

                    if done:
                        # Agent sent an event
                        try:
                            event = await agent_task
                            last_event_time = time.time()
                            yield event
                            # Create next agent task
                            agent_task = asyncio.create_task(agent_generator.__anext__())
                        except StopAsyncIteration:
                            # Agent is done
                            break
                    else:
                        # Timeout reached without event - send heartbeat
                        current_time = time.time()
                        if current_time - last_event_time >= heartbeat_interval:
                            yield {
                                "type": "heartbeat",
                                "timestamp": time.time() * 1000,
                                "message": "Connection alive"
                            }
                            last_event_time = current_time
            finally:
                heartbeat_task.cancel()

        try:
            agent = AutonomousAgent(
                workspace_path=workspace_path,
                api_key=api_key,
                provider=provider,
                model=model,
            )

            async for event in heartbeat_wrapper(
                agent.execute_task(
                    request=augmented_message,  # Use augmented message with image context
                    run_verification=request.run_verification,
                )
            ):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.exception(f"[NAVI Autonomous] Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
