"""
NAVI Orchestrator (AEP Production Version)
==========================================

This is the brain of the Autonomous Engineering Platform.

Responsibilities:
    • Accept incoming user messages
    • Classify intent using:
          1) LLMIntentClassifier (primary)
          2) IntentClassifier (fallback)
    • Retrieve long-term memory (optional)
    • Build planner context
    • Generate a plan with Planner v3
    • Execute each step through ToolExecutor
    • Save session state (optional)
    • Return structured AgentTurnResult for UI

This file replaces the older orchestrator and aligns with:
    backend/ai/llm_router.py
    backend/ai/intent_llm_classifier.py
    backend/agent/intent_classifier.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .intent_schema import NaviIntent
from .intent_classifier import IntentClassifier

logger = logging.getLogger(__name__)


# ============================================================================
# Optional Interfaces (State + Memory)
# ============================================================================


class StateManager(Protocol):
    def load_state(self, session_id: str) -> Dict[str, Any]: ...

    def save_state(self, session_id: str, state: Dict[str, Any]) -> None: ...


class MemoryRetriever(Protocol):
    def retrieve(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> Dict[str, Any]: ...


class Planner(Protocol):
    async def plan(
        self, intent: NaviIntent, context: Dict[str, Any]
    ) -> "PlanResult": ...


class ToolExecutor(Protocol):
    async def execute_step(
        self, step: "PlannedStep", intent: NaviIntent, context: Dict[str, Any]
    ) -> "StepResult": ...


class LLMIntentClassifier(Protocol):
    async def classify(
        self,
        message: Any,
        *,
        repo: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> NaviIntent: ...


# ============================================================================
# Planning Data Structures
# ============================================================================


@dataclass
class PlannedStep:
    """A single step produced by the planner."""

    id: str
    description: str
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    """Result from the planner containing steps and optional summary."""

    steps: List[PlannedStep]
    summary: Optional[str] = None


@dataclass
class StepResult:
    """Result from executing a single step."""

    step_id: str
    ok: bool
    output: Any
    error: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Result Container Returned to API/UI
# ============================================================================


@dataclass
class AgentTurnResult:
    intent: NaviIntent
    trace: List["StepResult"]
    final_message: str
    raw_plan_summary: Optional[str] = None


# ============================================================================
# Orchestrator Implementation
# ============================================================================


class NaviOrchestrator:
    """
    Production-grade orchestrator for NAVI (AEP).
    """

    def __init__(
        self,
        *,
        planner: "Planner",
        tool_executor: "ToolExecutor",
        llm_classifier: Optional["LLMIntentClassifier"] = None,
        heuristic_classifier: Optional[IntentClassifier] = None,
        state_manager: Optional[StateManager] = None,
        memory_retriever: Optional[MemoryRetriever] = None,
    ):
        self.planner = planner
        self.tool_executor = tool_executor

        # Intent classifiers
        self.llm_classifier = llm_classifier
        if not self.llm_classifier:
            try:
                from ..ai.intent_llm_classifier import LLMIntentClassifier

                self.llm_classifier = LLMIntentClassifier()
            except ImportError:
                logger.warning("LLM classifier not available, using heuristic only")

        self.heuristic_classifier = heuristic_classifier or IntentClassifier()

        # Optional components
        self.state_manager = state_manager
        self.memory_retriever = memory_retriever

    # ----------------------------------------------------------------------
    # Public API: full NAVI turn
    # ----------------------------------------------------------------------

    async def handle_message(
        self,
        *,
        session_id: str,
        message: Any,
        metadata: Optional[Dict[str, Any]] = None,
        repo: Optional[Any] = None,
        source: Optional[str] = "chat",
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        context_packet: Optional[Dict[str, Any]] = None,
    ) -> AgentTurnResult:

        # 1. Load session state if enabled
        state = {}
        if self.state_manager:
            try:
                state = self.state_manager.load_state(session_id)
            except Exception as e:
                logger.error(f"[STATE] Failed to load session state: {e}")
                state = {}

        # 2. Classify intent → Try LLM, fallback to heuristic
        try:
            if self.llm_classifier:
                intent = await self.llm_classifier.classify(
                    message,
                    metadata=metadata,
                    repo=repo,
                    api_key=api_key,
                    org_id=org_id,
                    session_id=session_id,
                )
            else:
                raise Exception("LLM classifier not available")
        except Exception as e:
            logger.error(f"[INTENT] LLM classifier failed → fallback. Error: {e}")
            intent = self.heuristic_classifier.classify(
                message, metadata=metadata, repo=repo
            )

        # 3. Retrieve long-term memory (optional)
        memory = {}
        if self.memory_retriever:
            try:
                memory = self.memory_retriever.retrieve(intent, {"state": state})
            except Exception as e:
                logger.error(f"[MEMORY] Memory retrieval failed: {e}")

        # 4. Build planner context
        planner_context = {
            "session_id": session_id,
            "state": state,
            "memory": memory,
            "metadata": metadata or {},
            "repo": repo,
            "source": source,
            "intent": intent,
            # Unified, source-linked context for this task/PR (when provided)
            "context_packet": context_packet,
        }

        # 5. Produce plan
        try:
            plan_result = await self.planner.plan(intent, planner_context)
        except Exception as e:
            logger.exception("[PLANNER] Error producing plan")
            return AgentTurnResult(
                intent=intent,
                trace=[],
                final_message=f"Failed to plan steps: {e}",
                raw_plan_summary=None,
            )

        # 6. Execute plan steps sequentially
        trace = []
        for step in plan_result.steps:
            try:
                step_result = await self.tool_executor.execute_step(
                    step,
                    intent=intent,
                    context=planner_context,
                )
                trace.append(step_result)

                if not step_result.ok:
                    logger.warning(
                        f"[EXECUTION] Step {step.id} failed: {step_result.error}"
                    )
            except Exception as e:
                logger.exception(
                    f"[EXECUTION] Tool execution failure for step {step.id}"
                )
                trace.append(
                    StepResult(step_id=step.id, ok=False, output=None, error=str(e))
                )

        # 7. Save updated state (if any changes)
        if self.state_manager:
            try:
                self.state_manager.save_state(session_id, state)
            except Exception as e:
                logger.error(f"[STATE] Failed to save session state: {e}")

        # 8. Produce final visible summary for UI
        final_msg = self._summarize_turn(intent, trace, plan_result.summary)

        return AgentTurnResult(
            intent=intent,
            trace=trace,
            final_message=final_msg,
            raw_plan_summary=plan_result.summary,
        )

    # ----------------------------------------------------------------------
    # Classification-only API
    # ----------------------------------------------------------------------

    async def classify(
        self,
        message: Any,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        repo: Optional[Any] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> NaviIntent:
        """
        Useful for the /api/intent/classify endpoint.
        """
        try:
            if self.llm_classifier:
                return await self.llm_classifier.classify(
                    message,
                    metadata=metadata,
                    repo=repo,
                    api_key=api_key,
                    org_id=org_id,
                    session_id=session_id,
                )
            else:
                raise Exception("LLM classifier not available")
        except Exception as e:
            logger.error(f"[INTENT] LLM classifier failed → fallback. Error: {e}")
            return self.heuristic_classifier.classify(
                message, metadata=metadata, repo=repo
            )

    # ----------------------------------------------------------------------
    # Private summary builder
    # ----------------------------------------------------------------------

    def _summarize_turn(
        self,
        intent: NaviIntent,
        trace: List["StepResult"],
        plan_summary: Optional[str],
    ) -> str:

        if not trace:
            return "Intent identified, but no steps were executed."

        total = len(trace)
        failures = [t for t in trace if not t.ok]
        successes = total - len(failures)

        parts = [
            f"Intent: {intent.family.value} / {intent.kind.value}.",
            f"Executed {total} step(s): {successes} succeeded, {len(failures)} failed.",
        ]

        if plan_summary:
            parts.append(f"Plan: {plan_summary}")

        if failures:
            first_err = failures[0]
            parts.append(
                f"First failure in step '{first_err.step_id}': {first_err.error}"
            )

        return " ".join(parts)


# ============================================================================
# Backwards Compatibility
# ============================================================================


async def run_agent_turn(
    session_id: str,
    message: Any,
    *,
    planner: "Planner",
    tool_executor: "ToolExecutor",
    repo: Optional[Any] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    state_manager: Optional[StateManager] = None,
    memory_retriever: Optional[MemoryRetriever] = None,
    context_packet: Optional[Dict[str, Any]] = None,
) -> AgentTurnResult:
    """
    Convenience wrapper for backwards compatibility.
    """
    orchestrator = NaviOrchestrator(
        planner=planner,
        tool_executor=tool_executor,
        state_manager=state_manager,
        memory_retriever=memory_retriever,
    )

    return await orchestrator.handle_message(
        session_id=session_id,
        message=message,
        repo=repo,
        source=source,
        metadata=metadata,
        context_packet=context_packet,
    )
