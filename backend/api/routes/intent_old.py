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
from backend.agent.orchestrator import (
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
# Request/Response Models
# ---------------------------------------------------------------------------

class ClassifyIntentRequest(BaseModel):
    """Request model for intent classification."""
    
    message: str = Field(..., description="User message to classify")
    
    # Model Configuration
    model: Optional[str] = Field(None, description="Specific model to use (e.g., 'claude-3-5-sonnet-20241022')")
    provider: Optional[str] = Field(None, description="Provider to use (e.g., 'anthropic', 'openai')")
    api_key: Optional[str] = Field(None, description="BYOK API key for the provider")
    org_id: Optional[str] = Field(None, description="Organization ID (OpenAI only)")
    use_smart_auto: bool = Field(True, description="Use SMART-AUTO model selection if no model specified")
    
    # Context
    repo_context: Optional[Dict[str, Any]] = Field(None, description="Repository context")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    # Classification Options
    use_llm: bool = Field(True, description="Use LLM classification (fallback to heuristic if fails)")
    include_confidence: bool = Field(True, description="Include confidence scores in response")


class ClassifyIntentResponse(BaseModel):
    """Response model for intent classification."""
    
    # Core Intent Data
    family: str = Field(..., description="Intent family (e.g., 'ENGINEERING')")
    kind: str = Field(..., description="Intent kind (e.g., 'IMPLEMENT_FEATURE')")
    priority: str = Field(..., description="Intent priority (e.g., 'NORMAL')")
    autonomy_mode: str = Field(..., description="Autonomy mode (e.g., 'ASSISTED')")
    
    # Classification Metadata
    confidence: float = Field(..., description="Classification confidence (0.0-1.0)")
    classification_method: str = Field(..., description="'llm' or 'heuristic'")
    raw_text: str = Field(..., description="Original message text")
    source: str = Field(..., description="Classification source")
    
    # Model Information (when LLM used)
    model_used: Optional[str] = Field(None, description="Model used for classification")
    provider_used: Optional[str] = Field(None, description="Provider used for classification")
    
    # Additional Data
    slots: Dict[str, Any] = Field(default_factory=dict, description="Extracted intent slots")
    workflow_hints: Optional[Dict[str, Any]] = Field(None, description="Workflow configuration hints")
    
    # Specs (when applicable)
    code_edit: Optional[Dict[str, Any]] = Field(None, description="Code editing specifications")
    test_run: Optional[Dict[str, Any]] = Field(None, description="Test execution specifications")
    project_mgmt: Optional[Dict[str, Any]] = Field(None, description="Project management specifications")


class ModelInfo(BaseModel):
    """Model information for UI display."""
    
    provider_id: str
    model_id: str
    display_name: str
    max_context: Optional[int] = None
    speed_index: Optional[int] = None
    cost_index: Optional[int] = None
    coding_accuracy: Optional[int] = None
    smart_auto_rank: Optional[int] = None
    recommended: bool = False
    type: Optional[str] = None


class ProviderInfo(BaseModel):
    """Provider information for UI display."""
    
    provider_id: str
    display_name: str
    base_url: str
    models: List[ModelInfo]


class ListModelsResponse(BaseModel):
    """Response for listing available models."""
    
    providers: List[ProviderInfo]
    smart_auto_candidates: List[ModelInfo]
    total_models: int
    last_updated: Optional[str] = None


class TestClassificationRequest(BaseModel):
    """Request for testing classification pipeline."""
    
    test_messages: List[str] = Field(..., description="List of test messages")
    model: Optional[str] = Field(None, description="Model to test with")
    provider: Optional[str] = Field(None, description="Provider to test with")
    api_key: Optional[str] = Field(None, description="API key for testing")
    compare_heuristic: bool = Field(True, description="Compare LLM vs heuristic results")


class TestResult(BaseModel):
    """Single test classification result."""
    
    message: str
    llm_result: Optional[ClassifyIntentResponse] = None
    heuristic_result: Optional[ClassifyIntentResponse] = None
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None


class TestClassificationResponse(BaseModel):
    """Response for classification testing."""
    
    results: List[TestResult]
    summary: Dict[str, Any]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/classify", response_model=ClassifyIntentResponse)
async def classify_intent(
    request: ClassifyIntentRequest,
    current_user: Any = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
) -> ClassifyIntentResponse:
    """
    Classify user intent with optional LLM model selection.
    
    This endpoint powers the NAVI agent's intent understanding.
    """
    
    try:
        # Create orchestrator with LLM support
        orchestrator = NaviOrchestrator(
            planner=SimplePlanner(),
            tool_executor=None,  # Not needed for classification only
            use_llm_classifier=request.use_llm,
            default_model=request.model,
            default_provider=request.provider,
            default_api_key=request.api_key,
            default_org_id=request.org_id,
        )
        
        # Perform async classification
        intent, classification_method = await orchestrator.classify_async(
            message=request.message,
            repo=request.repo_context,
            metadata=request.metadata,
            api_key=request.api_key,
            org_id=request.org_id,
            model=request.model,
            provider=request.provider,
            session_id=request.session_id,
        )
        
        # Convert NaviIntent to response model
        response = ClassifyIntentResponse(
            family=intent.family.value,
            kind=intent.kind.value,
            priority=intent.priority.value,
            autonomy_mode=intent.autonomy_mode.value,
            confidence=intent.confidence,
            classification_method=classification_method,
            raw_text=intent.raw_text,
            source=intent.source,
            model_used=request.model if classification_method == "llm" else None,
            provider_used=request.provider if classification_method == "llm" else None,
            slots=intent.slots,
        )
        
        # Add workflow hints if present
        if intent.workflow:
            response.workflow_hints = {
                "autonomy_mode": intent.workflow.autonomy_mode.value,
                "max_steps": intent.workflow.max_steps,
                "auto_run_tests": intent.workflow.auto_run_tests,
                "allow_cross_repo_changes": intent.workflow.allow_cross_repo_changes,
                "allow_long_running": intent.workflow.allow_long_running,
            }
        
        # Add spec details if present
        if intent.code_edit:
            response.code_edit = {
                "goal": intent.code_edit.goal,
                "primary_files": intent.code_edit.primary_files,
                "allowed_languages": intent.code_edit.allowed_languages,
            }
        
        if intent.test_run:
            response.test_run = {
                "command": intent.test_run.command,
                "only_if_files_changed": intent.test_run.only_if_files_changed,
            }
        
        if intent.project_mgmt:
            response.project_mgmt = {
                "tickets": intent.project_mgmt.tickets,
                "pr_number": intent.project_mgmt.pr_number,
                "notes_goal": intent.project_mgmt.notes_goal,
            }
        
        logger.info(f"[API] Classified intent via {classification_method}: {intent.family.value}/{intent.kind.value}")
        
        return response
        
    except Exception as e:
        logger.error(f"[API] Intent classification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Intent classification failed: {str(e)}"
        )


@router.get("/models", response_model=ListModelsResponse)
async def list_available_models() -> ListModelsResponse:
    """
    List all available LLM models for intent classification.
    
    Used by the UI to populate model selection dropdowns.
    """
    
    try:
        # Get all providers and models
        providers_data = []
        total_models = 0
        
        for provider_info in list_providers():
            models_data = []
            provider_models = list_models(provider_info.provider_id)
            
            for model_info in provider_models:
                models_data.append(ModelInfo(
                    provider_id=model_info.provider_id,
                    model_id=model_info.model_id,
                    display_name=model_info.display_name or model_info.model_id,
                    max_context=model_info.max_context,
                    speed_index=model_info.speed_index,
                    cost_index=model_info.cost_index,
                    coding_accuracy=model_info.coding_accuracy,
                    smart_auto_rank=model_info.smart_auto_rank,
                    recommended=model_info.recommended,
                    type=model_info.type,
                ))
            
            providers_data.append(ProviderInfo(
                provider_id=provider_info.provider_id,
                display_name=provider_info.display_name,
                base_url=provider_info.base_url,
                models=models_data,
            ))
            
            total_models += len(models_data)
        
        # Get smart auto candidates
        smart_candidates_data = []
        for candidate in smart_auto_candidates(limit=5):
            smart_candidates_data.append(ModelInfo(
                provider_id=candidate.provider_id,
                model_id=candidate.model_id,
                display_name=candidate.display_name or candidate.model_id,
                max_context=candidate.max_context,
                speed_index=candidate.speed_index,
                cost_index=candidate.cost_index,
                coding_accuracy=candidate.coding_accuracy,
                smart_auto_rank=candidate.smart_auto_rank,
                recommended=candidate.recommended,
                type=candidate.type,
            ))
        
        return ListModelsResponse(
            providers=providers_data,
            smart_auto_candidates=smart_candidates_data,
            total_models=total_models,
        )
        
    except Exception as e:
        logger.error(f"[API] Failed to list models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )


@router.post("/test", response_model=TestClassificationResponse)
async def test_classification_pipeline(
    request: TestClassificationRequest,
    current_user: Any = Depends(get_current_user),
) -> TestClassificationResponse:
    """
    Test the classification pipeline with multiple messages.
    
    Useful for comparing LLM vs heuristic classification accuracy.
    """
    
    try:
        results = []
        llm_successes = 0
        heuristic_successes = 0
        total_llm_time = 0.0
        total_heuristic_time = 0.0
        
        for message in request.test_messages:
            test_result = TestResult(message=message)
            
            try:
                # Test LLM classification
                if request.api_key:
                    import time
                    start_time = time.time()
                    
                    orchestrator = NaviOrchestrator(
                        planner=SimplePlanner(),
                        tool_executor=None,
                        use_llm_classifier=True,
                        default_model=request.model,
                        default_provider=request.provider,
                        default_api_key=request.api_key,
                    )
                    
                    intent, method = await orchestrator.classify_async(
                        message=message,
                        api_key=request.api_key,
                        model=request.model,
                        provider=request.provider,
                    )
                    
                    processing_time = (time.time() - start_time) * 1000
                    total_llm_time += processing_time
                    
                    test_result.llm_result = ClassifyIntentResponse(
                        family=intent.family.value,
                        kind=intent.kind.value,
                        priority=intent.priority.value,
                        autonomy_mode=intent.autonomy_mode.value,
                        confidence=intent.confidence,
                        classification_method=method,
                        raw_text=intent.raw_text,
                        source=intent.source,
                        model_used=request.model,
                        provider_used=request.provider,
                        slots=intent.slots,
                    )
                    test_result.processing_time_ms = processing_time
                    
                    if method == "llm":
                        llm_successes += 1
                
                # Test heuristic classification
                if request.compare_heuristic:
                    start_time = time.time()
                    
                    heuristic_orchestrator = NaviOrchestrator(
                        planner=SimplePlanner(),
                        tool_executor=None,
                        use_llm_classifier=False,
                    )
                    
                    heuristic_intent = heuristic_orchestrator.classify(message)
                    
                    heuristic_time = (time.time() - start_time) * 1000
                    total_heuristic_time += heuristic_time
                    
                    test_result.heuristic_result = ClassifyIntentResponse(
                        family=heuristic_intent.family.value,
                        kind=heuristic_intent.kind.value,
                        priority=heuristic_intent.priority.value,
                        autonomy_mode=heuristic_intent.autonomy_mode.value,
                        confidence=heuristic_intent.confidence,
                        classification_method="heuristic",
                        raw_text=heuristic_intent.raw_text,
                        source=heuristic_intent.source,
                        slots=heuristic_intent.slots,
                    )
                    
                    heuristic_successes += 1
                
            except Exception as e:
                test_result.error = str(e)
                logger.warning(f"[API] Test failed for message '{message}': {e}")
            
            results.append(test_result)
        
        # Generate summary
        summary = {
            "total_messages": len(request.test_messages),
            "llm_successes": llm_successes,
            "heuristic_successes": heuristic_successes,
            "avg_llm_time_ms": total_llm_time / max(llm_successes, 1),
            "avg_heuristic_time_ms": total_heuristic_time / max(heuristic_successes, 1),
            "llm_success_rate": llm_successes / len(request.test_messages),
            "heuristic_success_rate": heuristic_successes / len(request.test_messages),
        }
        
        return TestClassificationResponse(
            results=results,
            summary=summary,
        )
        
    except Exception as e:
        logger.error(f"[API] Classification testing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Classification testing failed: {str(e)}"
        )