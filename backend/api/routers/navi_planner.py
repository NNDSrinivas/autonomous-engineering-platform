"""
NAVI Planner API - Plan Mode Endpoints

Provides REST API for:
1. Creating plans with clarifying questions
2. Answering questions
3. Approving and executing plans
4. Streaming plan execution progress

This enables the workflow:
1. User submits request + optional UI screenshots
2. NAVI asks senior-engineer-level questions
3. User answers, NAVI generates structured plan
4. User approves, NAVI executes task-by-task
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import json
import asyncio
import logging

from backend.services.navi_planner import (
    create_plan,
    answer_plan_questions,
    approve_plan,
    execute_plan,
    get_plan_status,
    list_workspace_plans,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi/plan", tags=["NAVI Planner"])


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================


class ImageAttachment(BaseModel):
    """UI screenshot or design image"""

    filename: str = Field(..., description="Image filename")
    mime_type: str = Field(default="image/png", description="Image MIME type")
    data: str = Field(..., description="Base64-encoded image data")
    description: Optional[str] = Field(None, description="Optional description")


class CreatePlanRequest(BaseModel):
    """Request to create a new execution plan"""

    message: str = Field(..., description="User's natural language request")
    workspace_path: str = Field(..., description="Path to the workspace/project")
    images: List[ImageAttachment] = Field(
        default_factory=list, description="UI screenshots"
    )
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class AnswerQuestionsRequest(BaseModel):
    """Request to answer clarifying questions"""

    answers: Dict[str, str] = Field(..., description="Question ID -> Answer mapping")


class PlanResponse(BaseModel):
    """Response containing plan details"""

    id: str
    title: str
    summary: str
    status: str
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    project_type: Optional[str] = None
    detected_technologies: List[str] = Field(default_factory=list)
    unanswered_questions: int = 0
    completed_tasks: int = 0
    total_tasks: int = 0
    risk_level: str = "low"


# ============================================================
# ENDPOINTS
# ============================================================


@router.post("/create", response_model=PlanResponse)
async def create_execution_plan(request: CreatePlanRequest):
    """
    Create a new execution plan from a user request.

    This is the entry point for "plan mode". The response will include:
    - Clarifying questions (if needed)
    - Initial plan structure
    - Detected project context

    Example workflow:
    1. User: "Build a user dashboard with login"
    2. NAVI asks: "What auth method?", "What UI framework?", etc.
    3. User answers questions
    4. NAVI generates detailed task plan
    5. User approves
    6. NAVI executes

    If UI screenshots are provided, NAVI will:
    - Analyze the images to understand the desired layout
    - Ask specific UI implementation questions
    - Generate component-based task breakdown
    """
    try:
        # Convert image attachments to dict format
        attachments = [
            {
                "kind": "image",
                "filename": img.filename,
                "mime_type": img.mime_type,
                "data": img.data,
                "description": img.description,
            }
            for img in request.images
        ]

        plan = await create_plan(
            request=request.message,
            workspace_path=request.workspace_path,
            attachments=attachments,
            context=request.context,
        )

        return PlanResponse(**plan)

    except Exception as e:
        logger.error(f"Failed to create plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{plan_id}/answer", response_model=PlanResponse)
async def answer_questions(plan_id: str, request: AnswerQuestionsRequest):
    """
    Answer clarifying questions for a plan.

    Once all questions are answered, the plan status changes to "ready"
    and the detailed task breakdown is generated.

    Example:
    ```json
    {
        "answers": {
            "q1": "JWT tokens (stateless)",
            "q2": "PostgreSQL (relational, ACID)",
            "q3": "Core functionality only (ship fast)"
        }
    }
    ```
    """
    try:
        plan = await answer_plan_questions(plan_id, request.answers)
        return PlanResponse(**plan)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to answer questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{plan_id}/approve", response_model=PlanResponse)
async def approve_execution_plan(plan_id: str):
    """
    Approve a plan for execution.

    The plan must be in "ready" status (all questions answered).
    After approval, the plan can be executed.
    """
    try:
        plan = await approve_plan(plan_id)
        return PlanResponse(**plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to approve plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{plan_id}/execute")
async def execute_plan_endpoint(plan_id: str):
    """
    Execute an approved plan with streaming progress updates.

    Returns a Server-Sent Events (SSE) stream with:
    - task_start: When a task begins
    - task_complete: When a task finishes
    - task_failed: If a task fails
    - plan_complete: When the entire plan is done

    Example event:
    ```
    data: {"type": "task_start", "task_id": "task-1", "task_title": "Create API endpoint"}
    ```
    """
    # Check plan exists and is approved
    plan = get_plan_status(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    if plan["status"] not in ["approved", "in_progress"]:
        raise HTTPException(
            status_code=400,
            detail=f"Plan cannot be executed (status: {plan['status']})",
        )

    async def event_stream():
        """Generate SSE events for plan execution"""
        progress_queue = asyncio.Queue()

        async def on_progress(event: Dict[str, Any]):
            await progress_queue.put(event)

        # Start execution in background
        execution_task = asyncio.create_task(
            execute_plan(plan_id, on_progress=on_progress)
        )

        try:
            # Emit events as they come
            while True:
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"

                    if event.get("type") in ["plan_complete", "plan_failed"]:
                        break

                except asyncio.TimeoutError:
                    # Check if execution is done
                    if execution_task.done():
                        result = await execution_task
                        yield f"data: {json.dumps({'type': 'plan_complete', 'plan': result})}\n\n"
                        break
                    # Send keepalive
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            execution_task.cancel()
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str):
    """
    Get the current status and details of a plan.
    """
    plan = get_plan_status(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return PlanResponse(**plan)


@router.get("/workspace/{workspace_path:path}")
async def list_plans(workspace_path: str):
    """
    List all plans for a workspace.

    Returns plans sorted by creation date (newest first).
    """
    plans = list_workspace_plans(workspace_path)
    return {
        "plans": plans,
        "total": len(plans),
    }


@router.delete("/{plan_id}")
async def cancel_plan(plan_id: str):
    """
    Cancel a plan that's in progress or pending.
    """
    from backend.services.navi_planner import get_plan, store_plan, PlanStatus

    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    if plan.status in [PlanStatus.COMPLETED, PlanStatus.CANCELLED]:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel plan (status: {plan.status.value})"
        )

    plan.status = PlanStatus.CANCELLED
    store_plan(plan)

    return {"status": "cancelled", "plan_id": plan_id}


# ============================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================


@router.websocket("/{plan_id}/ws")
async def plan_websocket(websocket: WebSocket, plan_id: str):
    """
    WebSocket endpoint for real-time plan execution updates.

    Alternative to SSE for clients that prefer WebSocket.
    """
    await websocket.accept()

    plan = get_plan_status(plan_id)
    if not plan:
        await websocket.send_json({"error": f"Plan {plan_id} not found"})
        await websocket.close()
        return

    try:
        # Send initial plan state
        await websocket.send_json({"type": "plan_state", "plan": plan})

        # If plan is approved, start execution
        if plan["status"] == "approved":

            async def on_progress(event: Dict[str, Any]):
                await websocket.send_json(event)

            result = await execute_plan(plan_id, on_progress=on_progress)
            await websocket.send_json({"type": "plan_complete", "plan": result})

        # Listen for client messages (e.g., cancel requests)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if data.get("action") == "cancel":
                    # Handle cancel
                    await websocket.send_json({"type": "cancelled"})
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for plan {plan_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()
