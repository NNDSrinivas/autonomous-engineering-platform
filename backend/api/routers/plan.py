"""
Live Plan API - Real-time collaborative planning
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
import json
import asyncio
import logging
import os

from backend.core.db import get_db
from backend.database.models.live_plan import LivePlan
from backend.database.models.memory_graph import MemoryNode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plan", tags=["plan"])

# In-memory broadcast mechanism (replace with Redis in production)
# WARNING: This will NOT work in multi-server deployments!
# TODO: Implement Redis Pub/Sub for production horizontal scaling
_active_streams = {}  # {plan_id: [asyncio.Queue, ...]}

# Log warning on module load if production-like env detected
if os.getenv("ENV") in ["production", "prod", "staging"]:
    logger.warning(
        "Live Plan Mode using in-memory SSE broadcasting. "
        "This will NOT work with multiple server instances! "
        "Implement Redis Pub/Sub for production deployment."
    )


class StartPlanRequest(BaseModel):
    title: str
    description: Optional[str] = None
    participants: Optional[List[str]] = None


class AddStepRequest(BaseModel):
    plan_id: str
    text: str
    owner: Optional[str] = "system"


class PlanResponse(BaseModel):
    plan_id: str
    title: str
    description: Optional[str]
    steps: List[dict]
    participants: List[str]
    archived: bool
    created_at: str
    updated_at: str


@router.post("/start")
def start_plan(
    req: StartPlanRequest,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """Create a new live plan session"""
    plan_id = str(uuid4())

    plan = LivePlan(
        id=plan_id,
        org_id=x_org_id,
        title=req.title,
        description=req.description,
        steps=[],
        participants=req.participants or [],
        archived=False,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    # Audit log (if available)
    try:
        from backend.telemetry.metrics import plan_events_total

        plan_events_total.labels(event="PLAN_START", org_id=x_org_id).inc()
    except Exception:
        pass

    return {"plan_id": plan_id, "status": "started"}


@router.get("/{plan_id}")
def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """Get plan details"""
    plan = (
        db.query(LivePlan)
        .filter(LivePlan.id == plan_id, LivePlan.org_id == x_org_id)
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return plan.to_dict()


@router.post("/step")
async def add_step(
    req: AddStepRequest,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """Add a step to the plan and broadcast to all listeners"""
    plan = (
        db.query(LivePlan)
        .filter(LivePlan.id == req.plan_id, LivePlan.org_id == x_org_id)
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.archived:
        raise HTTPException(status_code=400, detail="Cannot modify archived plan")

    # Create step object with unique ID
    step = {
        "id": str(uuid4()),
        "text": req.text,
        "owner": req.owner,
        "ts": datetime.utcnow().isoformat(),
    }

    # Update plan - append to JSON array
    # NOTE: For plans with 50+ steps, consider using a separate steps table
    # or PostgreSQL's jsonb_insert for better performance
    # WARNING: This read-modify-write pattern has race condition potential under
    # concurrent writes. For production use with high concurrency, consider:
    # - PostgreSQL's native jsonb_set/jsonb_insert for atomic updates
    # - Optimistic locking with a version field to detect conflicts
    steps = plan.steps or []
    steps.append(step)
    plan.steps = steps
    plan.updated_at = datetime.utcnow()

    # Warn if plan is getting large (performance concern)
    # Use exponential thresholds to avoid log flooding: 50, 100, 200, 400, 800...
    step_count = len(steps)
    # Warn at explicit, exponentially-spaced thresholds to avoid frequent log noise
    # Note: Exact threshold matching intentionally used - if steps are added in batches
    # and skip a threshold, that's acceptable (reduces noise further)
    # Using set for O(1) lookup performance
    warning_thresholds = {50, 100, 200, 400, 800, 1600, 3200}
    if step_count in warning_thresholds:
        logger.warning(
            f"Plan {req.plan_id} has {step_count} steps. "
            "Consider migrating to a separate steps table for better performance."
        )

    db.commit()

    # Broadcast to all active streams
    if req.plan_id in _active_streams:
        for queue in _active_streams[req.plan_id]:
            try:
                await queue.put(step)
            except asyncio.QueueFull:
                logger.warning(
                    f"Queue for plan {req.plan_id} is full; step may be delayed or dropped"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error broadcasting step to plan {req.plan_id}: {e}",
                    exc_info=True,
                )

    # Metrics
    try:
        from backend.telemetry.metrics import plan_events_total

        plan_events_total.labels(event="PLAN_STEP", org_id=x_org_id).inc()
    except Exception:
        pass

    return {"status": "step_added", "step": step}


@router.get("/{plan_id}/stream")
async def stream_plan_updates(
    plan_id: str,
    x_org_id: str = Header(..., alias="X-Org-Id"),
    db: Session = Depends(get_db),
):
    """Server-Sent Events stream for real-time plan updates"""

    # Verify plan exists
    plan = (
        db.query(LivePlan)
        .filter(LivePlan.id == plan_id, LivePlan.org_id == x_org_id)
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Create queue for this connection
    queue = asyncio.Queue()

    # Register queue
    if plan_id not in _active_streams:
        _active_streams[plan_id] = []
    _active_streams[plan_id].append(queue)

    async def event_generator():
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'plan_id': plan_id})}\n\n"

            # Stream updates
            while True:
                step = await queue.get()
                yield f"data: {json.dumps(step)}\n\n"

        finally:
            # Cleanup
            if plan_id in _active_streams:
                try:
                    _active_streams[plan_id].remove(queue)
                    if not _active_streams[plan_id]:
                        del _active_streams[plan_id]
                except Exception:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{plan_id}/archive")
def archive_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """Archive plan and store in memory graph"""
    plan = (
        db.query(LivePlan)
        .filter(LivePlan.id == plan_id, LivePlan.org_id == x_org_id)
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.archived:
        # Idempotent: already archived, check for existing memory node
        node = (
            db.query(MemoryNode)
            .filter(
                MemoryNode.org_id == x_org_id,
                MemoryNode.kind == "plan_session",
                MemoryNode.foreign_id == plan_id,
            )
            .first()
        )

        if node:
            # Node exists, return success
            return {
                "status": "archived",
                "plan_id": plan_id,
                "memory_node_id": node.id,
            }

        # Edge case: Plan marked archived but memory node missing (previous failure)
        # Attempt to create the missing node to restore consistency
        logger.warning(
            f"Plan {plan_id} is archived but memory node missing - creating it now"
        )
        # Fall through to create the memory node below

    # Mark as archived (or already archived from edge case above)
    if not plan.archived:
        plan.archived = True
        plan.updated_at = datetime.utcnow()

    # Create memory graph node
    node = MemoryNode(
        org_id=x_org_id,
        kind="plan_session",
        foreign_id=plan_id,
        title=plan.title,
        summary=f"Plan with {len(plan.steps or [])} steps, {len(plan.participants or [])} participants",
        link=f"/plan/{plan_id}",
        content=json.dumps(
            {
                "title": plan.title,
                "description": plan.description,
                "steps": plan.steps or [],
                "participants": plan.participants or [],
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
                "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
                "plan_id": plan_id,
            }
        ),
        metadata={
            "steps_count": len(plan.steps or []),
            "participants": plan.participants,
            "archived_at": datetime.utcnow().isoformat(),
        },
        created_at=plan.created_at,
    )

    db.add(node)
    db.commit()

    # Metrics
    try:
        from backend.telemetry.metrics import plan_events_total

        plan_events_total.labels(event="PLAN_ARCHIVE", org_id=x_org_id).inc()
    except Exception:
        pass

    return {"status": "archived", "plan_id": plan_id, "memory_node_id": node.id}


@router.get("/list")
def list_plans(
    archived: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """List plans for organization"""
    query = db.query(LivePlan).filter(LivePlan.org_id == x_org_id)

    if archived is not None:
        query = query.filter(LivePlan.archived == archived)

    query = query.order_by(LivePlan.updated_at.desc()).limit(limit)

    plans = query.all()

    return {"plans": [p.to_dict() for p in plans], "count": len(plans)}
