"""
Intent & Agent routes for NAVI / AEP.

This module exposes two main endpoints:

    POST /api/agent/intent/preview
        → classify a message into NaviIntent (no tools executed)

    POST /api/agent/intent/run
        → full NAVI turn: classify → plan → tools → summary

The implementation is deliberately thin and delegates all heavy lifting to:

    - backend.agent.intent_classifier.IntentClassifier
    - backend.agent.orchestrator.NaviOrchestrator
    - backend.agent.planner (default planner factory)
    - backend.agent.tool_executor (default tool executor factory)
    - backend.agent.state_manager (optional)
    - backend.agent.memory_retriever (optional)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from backend.agent.intent_classifier import IntentClassifier, IntentClassifierConfig
from backend.agent.intent_schema import (
    IntentSource,
    NaviIntent,
    RepoTarget,
)
from backend.orchestrator import (
    AgentTurnResult,
    NaviOrchestrator,
    Planner,
    ToolExecutor,
    StateManager,
    MemoryRetriever,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/agent/intent", tags=["agent-intent"])

# ---------------------------------------------------------------------------
# Pydantic models for requests / responses
# ---------------------------------------------------------------------------


class IntentPreviewRequest(BaseModel):
    """
    Lightweight request just for classification.

    `message` is the raw user input. `metadata` carries optional hints
    such as files, language, tickets, etc. (see IntentClassifier docs).
    """

    message: Any = Field(..., description="User message or message-like object")
    repo: Optional[str] = Field(
        default=None,
        description="Optional repository identifier / path",
    )
    source: Optional[str] = Field(
        default="chat",
        description="Source of the request (chat, vscode, jetbrains, webhook, ...)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured hints for classification",
    )


class IntentPreviewResponse(BaseModel):
    intent: Dict[str, Any]


class AgentRunRequest(BaseModel):
    """
    Full agent turn request.

    `session_id` groups turns together (e.g. per chat thread or IDE
    workspace). `message` and `metadata` are passed through to the
    classifier + orchestrator.
    """

    session_id: str = Field(..., description="Logical session / conversation id")
    message: Any = Field(..., description="User message")
    repo: Optional[str] = Field(
        default=None,
        description="Optional repository identifier / path",
    )
    source: Optional[str] = Field(
        default="chat",
        description="Source of the request (chat, vscode, jetbrains, webhook, ...)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured hints (files, language, tickets, etc.)",
    )


class AgentRunResponse(BaseModel):
    result: Dict[str, Any]


# ---------------------------------------------------------------------------
# Factories for planner / executor / state / memory
# ---------------------------------------------------------------------------


def _create_default_planner() -> Planner:
    """
    Try to construct a reasonable default planner from backend.agent.planner
    without hard-coding a specific class name.

    This keeps the router compatible if you rename or upgrade the planner
    implementation later; just expose one of the expected names.
    """
    from backend.agent import planner as planner_module  # local import to avoid cycles

    candidate_names = (
        "NaviPlanner",
        "PlannerV3",
        "Planner",
        "AgentPlanner",
    )
    for name in candidate_names:
        cls = getattr(planner_module, name, None)
        if cls is not None:
            return cls()  # type: ignore[call-arg]
    raise RuntimeError(
        "No suitable planner implementation found in backend.agent.planner. "
        "Expose one of: " + ", ".join(candidate_names)
    )


def _create_default_tool_executor() -> ToolExecutor:
    """
    Same idea as planner: pick a sensible default tool executor implementation.
    """
    from backend.agent import tool_executor as tool_exec_module

    candidate_names = (
        "NaviToolExecutor",
        "ToolExecutorV2",
        "ToolExecutorV1",
        "ToolExecutor",
    )
    for name in candidate_names:
        cls = getattr(tool_exec_module, name, None)
        if cls is not None:
            return cls()  # type: ignore[call-arg]
    raise RuntimeError(
        "No suitable ToolExecutor implementation found in backend.agent.tool_executor. "
        "Expose one of: " + ", ".join(candidate_names)
    )


def _create_default_state_manager() -> Optional[StateManager]:
    """
    Optional: if you have a state manager (e.g. Redis, Postgres, in-memory),
    expose it here. If not, we just return None and NAVI will be stateless.
    """
    try:
        from backend.agent import state_manager as state_module
    except Exception:
        return None

    candidate_names = (
        "RedisStateManager",
        "DbStateManager",
        "InMemoryStateManager",
        "StateManager",
    )
    for name in candidate_names:
        cls = getattr(state_module, name, None)
        if cls is not None:
            return cls()  # type: ignore[call-arg]
    return None


def _create_default_memory_retriever() -> Optional[MemoryRetriever]:
    """
    Optional semantic / RAG memory retriever.
    """
    try:
        from backend.agent import memory_retriever as mem_module
    except Exception:
        return None

    candidate_names = (
        "NaviMemoryRetriever",
        "MemoryRetriever",
    )
    for name in candidate_names:
        cls = getattr(mem_module, name, None)
        if cls is not None:
            return cls()  # type: ignore[call-arg]
    return None


# ---------------------------------------------------------------------------
# Global orchestrator instance
# ---------------------------------------------------------------------------

_classifier = IntentClassifier(IntentClassifierConfig())
_orchestrator: Optional[NaviOrchestrator]
_orchestrator_init_error: Optional[str] = None

try:
    from backend.agent.planner_v3 import SimplePlanner
    from backend.agent.tool_executor_simple import SimpleToolExecutor

    _orchestrator = NaviOrchestrator(
        planner=SimplePlanner(),
        tool_executor=SimpleToolExecutor(),
        heuristic_classifier=_classifier,
        state_manager=None,  # Skip optional components for now
        memory_retriever=None,
    )
except Exception as exc:  # pragma: no cover - we want a clear runtime error
    _orchestrator = None
    _orchestrator_init_error = str(exc)


def get_orchestrator() -> NaviOrchestrator:
    if _orchestrator is None:
        raise HTTPException(
            status_code=500,
            detail=f"NAVI orchestrator not initialised: {_orchestrator_init_error}",
        )
    return _orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_intent_source(source: Optional[str]) -> IntentSource:
    if not source:
        return IntentSource.CHAT
    try:
        return IntentSource(source)
    except ValueError:
        # Fallback to CHAT for unknown values; keeps the API forgiving.
        return IntentSource.CHAT


def _to_repo_target(repo: Optional[str]) -> Optional[RepoTarget]:
    if not repo:
        return None
    # RepoTarget can carry more structure later; for now we treat it as an id.
    return RepoTarget(repo_id=repo)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/preview", response_model=IntentPreviewResponse)
async def preview_intent(
    payload: IntentPreviewRequest,
) -> IntentPreviewResponse:
    """
    Classify a message into a `NaviIntent` without running any tools.

    This is useful for:
        - debugging / observability
        - UI surfaces that want to show "what NAVI thinks this is"
        - analytics / routing decisions
    """
    repo_target = _to_repo_target(payload.repo)
    source = _to_intent_source(payload.source)

    intent: NaviIntent = _classifier.classify(
        message=payload.message,
        repo=repo_target,
        source=source,
        metadata=payload.metadata,
    )

    return IntentPreviewResponse(intent=jsonable_encoder(intent))


@router.post("/run", response_model=AgentRunResponse)
async def run_agent_turn(
    payload: AgentRunRequest,
    orchestrator: NaviOrchestrator = Depends(get_orchestrator),
) -> AgentRunResponse:
    """
    Full NAVI turn:

        1. Classify → NaviIntent
        2. Plan via planner
        3. Execute tools via ToolExecutor
        4. Summarise into final_message
    """
    repo_target = _to_repo_target(payload.repo)
    source = _to_intent_source(payload.source)

    result: AgentTurnResult = await orchestrator.handle_message(
        session_id=payload.session_id,
        message=payload.message,
        repo=repo_target,
        source=source,
        metadata=payload.metadata,
    )

    return AgentRunResponse(result=jsonable_encoder(result))
