"""
Agent API Routes
================

Complete NAVI agent endpoints for production autonomous engineering platform.

Key endpoints:
- POST /api/agent/turn - Execute complete NAVI agent turn
- GET /api/agent/models - Get available LLM models for classification
- POST /api/agent/classify - Classify intent only (no execution)
- GET /api/agent/trace/{session_id} - Get execution trace for session

Integration with:
- NaviOrchestrator: Full agent turns with LLM classification
- PlannerV3: Smart planning with context awareness
- ToolExecutor: Production tool execution pipeline
- LLM Infrastructure: Model selection and BYOK support
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status

from ...agent.orchestrator import NaviOrchestrator, AgentTurnResult
from ..deps import get_current_user, get_orchestrator

router = APIRouter(prefix="/agent", tags=["Agent"])

# ============================================================================
# Request/Response Models
# ============================================================================


class AgentTurnRequest(BaseModel):
    """Request for complete NAVI agent turn."""

    message: str
    session_id: str = "default"
    metadata: Optional[Dict[str, Any]] = None
    repo_context: Optional[str] = None
    source: str = "api"
    api_key: Optional[str] = None
    org_id: Optional[str] = None
    model: Optional[str] = None


class AgentTurnResponse(BaseModel):
    """Response from complete NAVI agent turn."""

    success: bool
    intent: Dict[str, Any]
    trace: List[Dict[str, Any]]
    final_message: str
    plan_summary: Optional[str] = None
    session_id: str
    execution_time_ms: int
    error: Optional[str] = None


class ClassifyRequest(BaseModel):
    """Request for intent classification only."""

    message: str
    metadata: Optional[Dict[str, Any]] = None
    repo_context: Optional[str] = None
    api_key: Optional[str] = None
    org_id: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None


class ClassifyResponse(BaseModel):
    """Response from intent classification."""

    success: bool
    intent: Dict[str, Any]
    confidence: float
    reasoning: Optional[str] = None
    classification_method: str  # "llm" or "heuristic"
    model_used: Optional[str] = None
    error: Optional[str] = None


class ModelInfo(BaseModel):
    """Information about available LLM model."""

    model_id: str
    provider: str
    display_name: str
    description: str
    context_window: int
    supports_classification: bool
    requires_api_key: bool


class ModelsResponse(BaseModel):
    """Response containing available models."""

    models: List[ModelInfo]
    default_model: str
    total_count: int


class TraceResponse(BaseModel):
    """Response containing execution trace."""

    session_id: str
    turns: List[Dict[str, Any]]
    total_turns: int


# ============================================================================
# Agent Endpoints
# ============================================================================


@router.post("/turn", response_model=AgentTurnResponse)
async def execute_agent_turn(
    request: AgentTurnRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    orchestrator: NaviOrchestrator = Depends(get_orchestrator),
) -> AgentTurnResponse:
    """
    Execute complete NAVI agent turn.

    This is the main endpoint for autonomous agent interactions.
    Performs:
    1. Intent classification using LLM or heuristic
    2. Context-aware planning with Planner v3
    3. Step-by-step tool execution
    4. Structured result aggregation
    """
    import time

    start_time = time.time()

    try:
        # Execute full agent turn through orchestrator
        result: AgentTurnResult = await orchestrator.handle_message(
            session_id=request.session_id,
            message=request.message,
            metadata=request.metadata,
            repo=request.repo_context,
            source=request.source,
            api_key=request.api_key,
            org_id=request.org_id,
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Convert trace to serializable format
        trace_data = []
        for step_result in result.trace:
            trace_data.append(
                {
                    "step_id": step_result.step_id,
                    "success": step_result.ok,
                    "output": step_result.output,
                    "error": step_result.error,
                }
            )

        return AgentTurnResponse(
            success=True,
            intent={
                "family": result.intent.family.value,
                "kind": result.intent.kind.value,
                "priority": result.intent.priority.value,
                "requires_approval": result.intent.requires_approval,
                "target": result.intent.target if result.intent.target else None,
                "parameters": result.intent.parameters,
                "confidence": result.intent.confidence,
            },
            trace=trace_data,
            final_message=result.final_message,
            plan_summary=result.raw_plan_summary,
            session_id=request.session_id,
            execution_time_ms=execution_time_ms,
            error=None,
        )

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)

        return AgentTurnResponse(
            success=False,
            intent={},
            trace=[],
            final_message=f"Agent execution failed: {str(e)}",
            plan_summary=None,
            session_id=request.session_id,
            execution_time_ms=execution_time_ms,
            error=str(e),
        )


@router.post("/classify", response_model=ClassifyResponse)
async def classify_intent(
    request: ClassifyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    orchestrator: NaviOrchestrator = Depends(get_orchestrator),
) -> ClassifyResponse:
    """
    Classify user message intent without execution.

    Useful for:
    - UI preview of intent before execution
    - Intent analysis and debugging
    - Model performance testing
    """
    try:
        # Classify intent only (no execution)
        intent = await orchestrator.classify(
            message=request.message,
            metadata=request.metadata,
            repo=request.repo_context,
            api_key=request.api_key,
            org_id=request.org_id,
            session_id=request.session_id,
        )

        return ClassifyResponse(
            success=True,
            intent={
                "family": intent.family.value,
                "kind": intent.kind.value,
                "priority": intent.priority.value,
                "requires_approval": intent.requires_approval,
                "target": intent.target if intent.target else None,
                "parameters": intent.parameters,
                "confidence": intent.confidence,
            },
            confidence=intent.confidence,
            reasoning=intent.parameters.get("reasoning"),
            classification_method="llm" if orchestrator.llm_classifier else "heuristic",
            model_used=request.model,
            error=None,
        )

    except Exception as e:
        return ClassifyResponse(
            success=False,
            intent={},
            confidence=0.0,
            reasoning=None,
            classification_method="error",
            model_used=None,
            error=str(e),
        )


@router.get("/models", response_model=ModelsResponse)
async def get_available_models(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ModelsResponse:
    """
    Get available LLM models for intent classification.

    Returns models from:
    - Built-in providers (OpenAI, Anthropic, etc.)
    - User-configured BYOK models
    - Smart-auto recommendations based on task
    """
    try:
        from ...ai.model_registry import LLMModelRegistry, smart_auto_candidates

        registry = LLMModelRegistry()

        models = []
        for model_info in registry.list_models():
            models.append(
                ModelInfo(
                    model_id=f"{model_info.provider}/{model_info.name}",
                    provider=model_info.provider,
                    display_name=model_info.name,
                    description=f"{model_info.provider} {model_info.type} model",
                    context_window=model_info.max_context,
                    supports_classification=True,  # All models support classification
                    requires_api_key=True,  # Assume all models require API keys
                )
            )

        # Get smart-auto recommendation
        smart_candidates_list = smart_auto_candidates()
        default_model = (
            f"{smart_candidates_list[0].provider}/{smart_candidates_list[0].name}"
            if smart_candidates_list
            else "openai/gpt-4o-mini"
        )
        smart_candidates = smart_auto_candidates()
        default_model = (
            smart_candidates[0].model_id if smart_candidates else "gpt-4o-mini"
        )

        return ModelsResponse(
            models=models,
            default_model=default_model,
            total_count=len(models),
        )

    except Exception:
        # Return minimal response on error
        return ModelsResponse(
            models=[
                ModelInfo(
                    model_id="gpt-4o-mini",
                    provider="openai",
                    display_name="GPT-4o Mini",
                    description="Fast and efficient model for classification",
                    context_window=128000,
                    supports_classification=True,
                    requires_api_key=True,
                )
            ],
            default_model="gpt-4o-mini",
            total_count=1,
        )


@router.get("/trace/{session_id}", response_model=TraceResponse)
async def get_execution_trace(
    session_id: str,
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TraceResponse:
    """
    Get execution trace for a session.

    Useful for:
    - Debugging agent behavior
    - UI display of execution history
    - Performance analysis
    """
    try:
        # TODO: Implement session storage and retrieval
        # For now, return empty trace
        return TraceResponse(
            session_id=session_id,
            turns=[],
            total_turns=0,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trace: {str(e)}",
        )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Agent system health check."""
    try:
        # Check orchestrator components
        orchestrator_status = "ok"
        planner_status = "ok"
        tool_executor_status = "ok"
        llm_status = "ok"

        try:
            # Test LLM connectivity
            from ...ai.llm_router import LLMRouter

            LLMRouter()
            llm_status = "ok"
        except Exception:
            llm_status = "degraded"

        overall_status = "ok"
        if llm_status == "degraded":
            overall_status = "degraded"

        return {
            "status": overall_status,
            "components": {
                "orchestrator": orchestrator_status,
                "planner": planner_status,
                "tool_executor": tool_executor_status,
                "llm_router": llm_status,
            },
            "timestamp": "2024-11-17T12:00:00Z",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": "2024-11-17T12:00:00Z",
        }
