"""
NAVI Enhanced API - RAG, Vision, Testing, and Persistence

Provides REST endpoints for:
1. Workspace RAG - Semantic code search
2. Vision Analysis - UI screenshot processing
3. Test Execution - Run and verify tests
4. Plan Persistence - Save/load/checkpoint plans

These endpoints enhance NAVI's "world-class pair programmer" capabilities.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
import logging

# Import services
from backend.services.workspace_rag import (
    index_workspace,
    search_codebase,
    get_context_for_task,
    get_index,
)
from backend.services.vision_service import (
    analyze_ui_screenshot,
    generate_code_from_ui,
)
from backend.services.test_executor import (
    run_tests,
    run_single_test,
    discover_tests,
    verify_tests_pass,
)
from backend.services.plan_persistence import (
    save_plan,
    load_plan,
    list_plans,
    delete_plan,
    create_checkpoint,
    get_latest_checkpoint,
    restore_checkpoint,
    list_checkpoints,
    log_execution,
    get_execution_logs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi/enhanced", tags=["NAVI Enhanced"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================


# RAG Models
class IndexWorkspaceRequest(BaseModel):
    workspace_path: str = Field(..., description="Path to workspace")
    force_reindex: bool = Field(default=False, description="Force re-indexing")


class SearchCodebaseRequest(BaseModel):
    workspace_path: str = Field(..., description="Path to workspace")
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=10, description="Number of results")


class GetContextRequest(BaseModel):
    workspace_path: str = Field(..., description="Path to workspace")
    task_description: str = Field(..., description="Task description")
    max_tokens: int = Field(default=8000, description="Max context tokens")


# Vision Models
class AnalyzeUIRequest(BaseModel):
    image_data: str = Field(..., description="Base64-encoded image")
    context: str = Field(default="", description="Additional context")
    provider: str = Field(default="anthropic", description="Vision provider")


class GenerateUICodeRequest(BaseModel):
    image_data: str = Field(..., description="Base64-encoded image")
    framework: str = Field(default="react", description="Target framework")
    css_framework: str = Field(default="tailwind", description="CSS framework")
    provider: str = Field(default="anthropic", description="Vision provider")


# Test Models
class RunTestsRequest(BaseModel):
    workspace_path: str = Field(..., description="Path to workspace")
    with_coverage: bool = Field(default=False, description="Collect coverage")
    test_filter: Optional[str] = Field(None, description="Test filter")


class RunSingleTestRequest(BaseModel):
    workspace_path: str = Field(..., description="Path to workspace")
    test_path: str = Field(..., description="Path to test file")
    test_name: Optional[str] = Field(None, description="Specific test name")


# Persistence Models
class SavePlanRequest(BaseModel):
    plan: Dict[str, Any] = Field(..., description="Plan data")


class CreateCheckpointRequest(BaseModel):
    plan_id: str = Field(..., description="Plan ID")
    task_id: Optional[str] = Field(None, description="Current task ID")
    checkpoint_type: str = Field(default="manual", description="Checkpoint type")


class LogExecutionRequest(BaseModel):
    plan_id: str = Field(..., description="Plan ID")
    log_type: str = Field(..., description="Log type (info, warning, error)")
    message: str = Field(..., description="Log message")
    task_id: Optional[str] = Field(None, description="Task ID")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


# ============================================================
# RAG ENDPOINTS
# ============================================================


@router.post("/rag/index")
async def index_workspace_endpoint(
    request: IndexWorkspaceRequest, background_tasks: BackgroundTasks
):
    """
    Index a workspace for semantic code search.

    This creates embeddings for all code files, enabling:
    - Semantic search across the entire codebase
    - Understanding of code relationships
    - Context-aware suggestions

    For large codebases, this runs in the background.
    """
    try:
        # Check if already indexed
        existing = get_index(request.workspace_path)
        if existing and not request.force_reindex:
            return {
                "status": "already_indexed",
                "index": existing.to_dict(),
            }

        # Start indexing
        result = await index_workspace(
            request.workspace_path,
            force_reindex=request.force_reindex,
        )

        return {
            "status": "indexed",
            "index": result,
        }

    except Exception as e:
        logger.error(f"Index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/search")
async def search_codebase_endpoint(request: SearchCodebaseRequest):
    """
    Search the codebase semantically.

    Unlike grep/ripgrep, this understands:
    - Natural language queries ("find authentication logic")
    - Code concepts ("where is user validation done")
    - Related code even without exact keyword matches
    """
    try:
        results = await search_codebase(
            request.workspace_path,
            request.query,
            top_k=request.top_k,
        )

        return {
            "query": request.query,
            "results": results,
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/context")
async def get_task_context_endpoint(request: GetContextRequest):
    """
    Get relevant codebase context for a task.

    This is what NAVI uses to understand how to implement
    features that fit with the existing codebase.
    """
    try:
        context = await get_context_for_task(
            request.workspace_path,
            request.task_description,
            max_context_tokens=request.max_tokens,
        )

        return {
            "task": request.task_description,
            "context": context,
            "token_estimate": len(context) // 4,
        }

    except Exception as e:
        logger.error(f"Context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/status/{workspace_path:path}")
async def get_index_status(workspace_path: str):
    """Get the indexing status for a workspace"""
    existing = get_index(workspace_path)

    if existing:
        return {
            "indexed": True,
            "stats": existing.to_dict(),
        }
    else:
        return {
            "indexed": False,
            "stats": None,
        }


# ============================================================
# VISION ENDPOINTS
# ============================================================


@router.post("/vision/analyze")
async def analyze_ui_endpoint(request: AnalyzeUIRequest):
    """
    Analyze a UI screenshot.

    Returns structured information about:
    - Layout structure
    - Components detected
    - Color scheme
    - Implementation suggestions

    Supports multiple vision providers:
    - anthropic: Claude 3.5 Sonnet (default)
    - openai: GPT-4 Vision
    - google: Gemini Pro Vision
    """
    try:
        analysis = await analyze_ui_screenshot(
            request.image_data,
            context=request.context,
            provider=request.provider,
        )

        return {
            "success": True,
            "analysis": analysis,
        }

    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vision/generate-code")
async def generate_code_from_ui_endpoint(request: GenerateUICodeRequest):
    """
    Generate component code from a UI screenshot.

    Analyzes the screenshot and generates:
    - React/Vue/etc component code
    - Tailwind/CSS styling
    - TypeScript types
    - Accessibility attributes
    """
    try:
        result = await generate_code_from_ui(
            request.image_data,
            framework=request.framework,
            css_framework=request.css_framework,
            provider=request.provider,
        )

        return {
            "success": True,
            "code": result["code"],
            "analysis": result["analysis"],
            "framework": result["framework"],
        }

    except Exception as e:
        logger.error(f"Code generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# TEST EXECUTION ENDPOINTS
# ============================================================


@router.post("/tests/run")
async def run_tests_endpoint(request: RunTestsRequest):
    """
    Run all tests in a workspace.

    Auto-detects the test framework (pytest, jest, go test, etc.)
    and runs tests with optional coverage collection.

    Returns:
    - Pass/fail counts
    - Failed test details with error messages
    - Coverage percentage (if requested)
    - Fix suggestions for failures
    """
    try:
        result = await run_tests(
            request.workspace_path,
            with_coverage=request.with_coverage,
            test_filter=request.test_filter,
        )

        return result

    except Exception as e:
        logger.error(f"Test execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/run-single")
async def run_single_test_endpoint(request: RunSingleTestRequest):
    """
    Run a single test file or test case.

    Useful for:
    - Running tests for a specific file
    - Re-running a failed test
    - Quick verification during development
    """
    try:
        result = await run_single_test(
            request.workspace_path,
            request.test_path,
            test_name=request.test_name,
        )

        return result

    except Exception as e:
        logger.error(f"Single test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/discover/{workspace_path:path}")
async def discover_tests_endpoint(workspace_path: str):
    """
    Discover tests in a workspace.

    Returns:
    - Detected test framework
    - List of test files
    - Test count
    """
    try:
        discovery = discover_tests(workspace_path)
        return discovery

    except Exception as e:
        logger.error(f"Test discovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/verify")
async def verify_tests_endpoint(request: RunTestsRequest):
    """
    Verify all tests pass.

    This is what NAVI uses after generating code to ensure
    it works correctly. Returns success/failure with details.
    """
    try:
        success, result = await verify_tests_pass(request.workspace_path)

        return {
            "success": success,
            "result": result,
        }

    except Exception as e:
        logger.error(f"Test verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PERSISTENCE ENDPOINTS
# ============================================================


@router.post("/plans/save")
async def save_plan_endpoint(request: SavePlanRequest):
    """
    Save a plan to persistent storage.

    Plans are stored in SQLite and survive:
    - Server restarts
    - Session changes
    - Crashes
    """
    try:
        save_plan(request.plan)
        return {"status": "saved", "plan_id": request.plan.get("id")}

    except Exception as e:
        logger.error(f"Save plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans/{plan_id}")
async def load_plan_endpoint(plan_id: str):
    """Load a plan from persistent storage"""
    try:
        plan = load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return plan

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Load plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans")
async def list_plans_endpoint(
    workspace_path: Optional[str] = None,
    status: Optional[str] = None,
):
    """List plans with optional filters"""
    try:
        plans = list_plans(workspace_path, status)
        return {"plans": plans, "count": len(plans)}

    except Exception as e:
        logger.error(f"List plans error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/plans/{plan_id}")
async def delete_plan_endpoint(plan_id: str):
    """Delete a plan"""
    try:
        deleted = delete_plan(plan_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Plan not found")
        return {"status": "deleted", "plan_id": plan_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Checkpoint endpoints
@router.post("/checkpoints/create")
async def create_checkpoint_endpoint(request: CreateCheckpointRequest):
    """
    Create a checkpoint of the current plan state.

    Use this to save progress before risky operations.
    """
    try:
        checkpoint_id = create_checkpoint(
            request.plan_id,
            task_id=request.task_id,
            checkpoint_type=request.checkpoint_type,
        )
        return {"status": "created", "checkpoint_id": checkpoint_id}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Create checkpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints/{plan_id}")
async def list_checkpoints_endpoint(plan_id: str):
    """List all checkpoints for a plan"""
    try:
        checkpoints = list_checkpoints(plan_id)
        return {"checkpoints": checkpoints, "count": len(checkpoints)}

    except Exception as e:
        logger.error(f"List checkpoints error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints/{plan_id}/latest")
async def get_latest_checkpoint_endpoint(plan_id: str):
    """Get the latest checkpoint for a plan"""
    try:
        checkpoint = get_latest_checkpoint(plan_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="No checkpoints found")
        return checkpoint

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get checkpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checkpoints/{checkpoint_id}/restore")
async def restore_checkpoint_endpoint(checkpoint_id: int):
    """
    Restore a plan from a checkpoint.

    Use this to roll back to a previous state after failures.
    """
    try:
        plan = restore_checkpoint(checkpoint_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        return {"status": "restored", "plan": plan}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Restore checkpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Execution logging endpoints
@router.post("/logs")
async def log_execution_endpoint(request: LogExecutionRequest):
    """Log an execution event"""
    try:
        log_execution(
            request.plan_id,
            request.log_type,
            request.message,
            task_id=request.task_id,
            details=request.details,
        )
        return {"status": "logged"}

    except Exception as e:
        logger.error(f"Log execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{plan_id}")
async def get_logs_endpoint(
    plan_id: str,
    task_id: Optional[str] = None,
    log_type: Optional[str] = None,
):
    """Get execution logs for a plan"""
    try:
        logs = get_execution_logs(plan_id, task_id, log_type)
        return {"logs": logs, "count": len(logs)}

    except Exception as e:
        logger.error(f"Get logs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
