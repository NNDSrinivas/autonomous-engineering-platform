"""
Live Plan API - Real-time collaborative planning
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
import json
import asyncio
import logging

from backend.core.db import get_db
from backend.core.security import sanitize_for_logging
from backend.core.settings import settings
from backend.database.models.live_plan import LivePlan
from backend.database.models.memory_graph import MemoryNode
from backend.api.deps import get_broadcaster
from backend.infra.broadcast.base import Broadcast
from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.api.security import check_policy_inline
from backend.core.policy.engine import PolicyEngine, get_policy_engine
from backend.core.db_utils import get_short_lived_session
from backend.core.audit.publisher import append_and_broadcast
from backend.core.eventstore.service import replay


def normalize_event_payload(data: dict) -> dict:
    """
    Extract and normalize event payload from SSE message data.
    Prioritizes nested payload structure to match backfilled events.

    Args:
        data: Raw event data dictionary

    Returns:
        Normalized payload dictionary
    """
    # Use consistent payload extraction - prioritize nested payload structure to match backfilled events
    payload = data.get("payload")
    if payload is None:
        # Fallback: if no nested payload, exclude metadata fields to avoid duplication
        payload = {k: v for k, v in data.items() if k not in ("seq", "type")}
    return payload


def parse_broadcaster_message(msg: str | dict) -> dict:
    """
    Parse message from broadcaster, handling both JSON strings and parsed dicts.

    Args:
        msg: Message from broadcaster (str or dict)

    Returns:
        Parsed message as dictionary

    Note:
        This helper consolidates the parsing logic to avoid redundant checks.
        TODO(tech-debt, P2): Standardize broadcaster output format to always return dicts
        and eliminate the need for this parsing step. This affects SSE message handling
        across the codebase. Priority: P2 (not blocking, but improves maintainability).
        Related: Dual-type (str | dict) workaround should be removed in future refactoring.
    """
    if isinstance(msg, str):
        result = json.loads(msg)
        if not isinstance(result, dict):
            raise ValueError(
                f"Parsed broadcaster message must be a dict, got {sanitize_for_logging(type(result).__name__)}"
            )
        return result
    # Validate that non-string input is actually a dict
    if not isinstance(msg, dict):
        raise TypeError(
            f"Expected str or dict, got {sanitize_for_logging(type(msg).__name__)}"
        )
    return msg


def format_sse_event(seq: Optional[int], event_type: str, payload: dict) -> str:
    """
    Format SSE event with consistent structure.

    Args:
        seq: Sequence ID for Last-Event-ID compatibility (optional)
        event_type: Event type
        payload: Event payload data

    Returns:
        Formatted SSE event string
    """
    lines = []
    if seq is not None:
        lines.append(f"id: {seq}\n")
    lines.append(f"event: {event_type}\n")
    lines.append(
        f"data: {json.dumps({'seq': seq, 'type': event_type, 'payload': payload})}\n\n"
    )
    return "".join(lines)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plan", tags=["plan"])


def _safe_isoformat(dt_obj):
    """Safely convert datetime to ISO format, handling None and Column types"""
    if dt_obj is None:
        return None
    try:
        return dt_obj.isoformat() if hasattr(dt_obj, "isoformat") else None
    except Exception:
        return None


def _channel(plan_id: str) -> str:
    """Generate Redis/broadcast channel name for a plan."""
    return f"{settings.PLAN_CHANNEL_PREFIX}{plan_id}"


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
    user: User = Depends(require_role(Role.PLANNER)),
):
    """Create a new live plan session (requires planner role)"""
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


@router.get("/list")
def list_plans(
    archived: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
    user: User = Depends(require_role(Role.VIEWER)),
):
    """List plans for organization (requires viewer role)"""
    query = db.query(LivePlan).filter(LivePlan.org_id == x_org_id)

    if archived is not None:
        query = query.filter(LivePlan.archived == archived)

    query = query.order_by(LivePlan.updated_at.desc()).limit(limit)

    plans = query.all()

    return {"plans": [p.to_dict() for p in plans], "count": len(plans)}


@router.get("/{plan_id}")
def get_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    x_org_id: str = Header(..., alias="X-Org-Id"),
    user: User = Depends(require_role(Role.VIEWER)),
):
    """Get plan details (requires viewer role)"""
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
    bc: Broadcast = Depends(get_broadcaster),
    user: User = Depends(require_role(Role.PLANNER)),
    policy_engine: PolicyEngine = Depends(get_policy_engine),
):
    """Add a step to the plan and broadcast to all listeners (requires planner role + policy check)"""

    # Verify plan exists before policy check to avoid information disclosure:
    # return 404 for non-existent plans, 403 for policy violations.
    plan = (
        db.query(LivePlan)
        .filter(LivePlan.id == req.plan_id, LivePlan.org_id == x_org_id)
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Use getattr to handle SQLAlchemy Column types properly
    if getattr(plan, "archived", False):
        raise HTTPException(status_code=400, detail="Cannot modify archived plan")

    # Check policy guardrails before modifying plan
    check_policy_inline(
        "plan.add_step",
        {"plan_id": req.plan_id, "step_name": req.text},
        policy_engine,
    )

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
    steps = getattr(plan, "steps", []) or []
    steps.append(step)
    setattr(plan, "steps", steps)
    setattr(plan, "updated_at", datetime.utcnow())

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
            "Plan %s has %d steps. Consider migrating to a separate steps table for better performance.",
            sanitize_for_logging(req.plan_id),
            step_count,
        )

    db.commit()

    # Append to event store and broadcast (PR-25: Audit & Replay)
    try:
        await append_and_broadcast(
            db,
            bc=bc,
            plan_id=req.plan_id,
            type="step",
            payload=step,
            user_sub=user.user_id,
            org_key=user.org_id,
        )
    except Exception as e:
        # Log but don't fail - backward compatibility
        logger.error(
            "Failed to append/broadcast step for plan %s: %s",
            sanitize_for_logging(req.plan_id),
            str(e),
            exc_info=True,
        )
        # Fallback to old broadcast method
        channel = _channel(req.plan_id)
        try:
            await bc.publish(channel, json.dumps(step))
        except Exception as fallback_error:
            logger.error(
                "Fallback broadcast also failed for plan %s: %s",
                sanitize_for_logging(req.plan_id),
                str(fallback_error),
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
    request: Request,
    x_org_id: str = Header(..., alias="X-Org-Id"),
    user: User = Depends(require_role(Role.VIEWER)),
    bc: Broadcast = Depends(get_broadcaster),
    since: Optional[int] = Query(
        None, description="Backfill events since this sequence number"
    ),
):
    """
    Server-Sent Events stream for real-time plan updates with auto-resume support.

    Supports Last-Event-ID header and ?since= query parameter for backfilling missed events.
    Emits id: <seq> lines for browser auto-resume capability.
    """

    # Discover resume point (header has precedence over query param)
    last_id_header = request.headers.get("Last-Event-ID")
    since_seq = None
    try:
        if last_id_header:
            since_seq = int(last_id_header)
        elif since is not None:
            since_seq = int(since)
    except ValueError:
        # Only compute resume_value in error path for better performance
        resume_value = last_id_header or since
        # Sanitize user input to prevent log injection
        sanitized_resume_value = sanitize_for_logging(str(resume_value))
        logger.warning(
            "Invalid sequence number in resume request: %s",
            sanitized_resume_value,
        )
        since_seq = None

    # Verify plan exists with a short-lived session that closes before streaming
    # IMPORTANT: SSE streams are long-lived connections that must not hold
    # database sessions/connections for their entire duration.
    #
    # NOTE: There is a theoretical race condition where the plan could be deleted
    # between this validation check and when clients consume the stream. This is
    # acceptable edge-case behavior since:
    # 1. Plan deletion is rare in production workflows
    # 2. Clients will simply receive no further updates if plan is deleted
    # 3. Implementing soft-delete with 'archived' flag would add complexity
    #    without significant benefit for the current use case
    with get_short_lived_session() as db:
        plan = (
            db.query(LivePlan)
            .filter(LivePlan.id == plan_id, LivePlan.org_id == x_org_id)
            .first()
        )

        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

    channel = _channel(plan_id)

    async def event_generator():
        try:
            # Optional backfill from event store
            if since_seq is not None:
                try:
                    with get_short_lived_session() as db:
                        events = replay(
                            session=db,
                            plan_id=plan_id,
                            since_seq=since_seq,
                            org_key=x_org_id,
                        )
                        for event in events:
                            # Emit with sequence ID for Last-Event-ID compatibility
                            yield format_sse_event(event.seq, event.type, event.payload)
                except Exception as e:
                    logger.error(
                        "Error during backfill replay for plan %s: %s",
                        sanitize_for_logging(plan_id),
                        str(e),
                        exc_info=True,
                    )
                    # Continue with SSE stream even if backfill fails

            # Always send initial connection message after any backfill
            yield f"data: {json.dumps({'seq': None, 'type': 'connected', 'payload': {'plan_id': plan_id}})}\n\n"

            # Stream live updates from broadcaster
            subscription = await bc.subscribe(channel)
            async for msg in subscription:
                try:
                    # Parse message using helper function to consolidate parsing logic
                    data = parse_broadcaster_message(msg)
                    seq = data.get("seq")
                    event_type = data.get("type", "message")
                    payload = normalize_event_payload(data)

                    # Emit with sequence ID for Last-Event-ID compatibility
                    yield format_sse_event(seq, event_type, payload)
                except (
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as e:
                    # Fallback for malformed messages - catch specific parsing errors:
                    #   - json.JSONDecodeError: message is not valid JSON
                    #   - KeyError: expected field missing from message dict
                    #   - TypeError: message is not a dict or has wrong type (e.g., runtime type validation)
                    #   - ValueError: unexpected value in message (e.g., invalid format)
                    # Note: AttributeError removed as it indicates programming bugs, not malformed data
                    # Trade-off: TypeError/ValueError could mask programming bugs, but catching them here
                    # prevents SSE stream breaks from broadcaster format issues. Alternative would be
                    # more granular try-except blocks around each parsing step (future improvement).
                    logger.warning(
                        "Malformed SSE message: %s (Error: %s)",
                        sanitize_for_logging(str(msg)),
                        str(e),
                        exc_info=True,
                    )

                    # Provide error info for client debugging without retrying parse
                    error_payload = {
                        "error": "Failed to parse SSE event data",
                        "raw": sanitize_for_logging(str(msg)),
                    }

                    yield "event: error\n"
                    yield f"data: {json.dumps(error_payload)}\n\n"

        except asyncio.CancelledError:
            # Client disconnected
            logger.debug(
                "SSE connection cancelled for plan %s", sanitize_for_logging(plan_id)
            )
            raise

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
    user: User = Depends(require_role(Role.PLANNER)),
):
    """Archive plan and store in memory graph (requires planner role)"""
    plan = (
        db.query(LivePlan)
        .filter(LivePlan.id == plan_id, LivePlan.org_id == x_org_id)
        .first()
    )

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Use getattr to handle SQLAlchemy Column types properly
    if getattr(plan, "archived", False):
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
            "Plan %s is archived but memory node missing - creating it now",
            sanitize_for_logging(plan_id),
        )
        # Fall through to create the memory node below

    # Mark as archived (or already archived from edge case above)
    if not getattr(plan, "archived", False):
        setattr(plan, "archived", True)
        setattr(plan, "updated_at", datetime.utcnow())

    # Create memory graph node
    node = MemoryNode(
        org_id=x_org_id,
        kind="plan_session",
        foreign_id=plan_id,
        title=plan.title,
        summary=f"Plan with {len(getattr(plan, 'steps', []) or [])} steps, {len(getattr(plan, 'participants', []) or [])} participants",
        link=f"/plan/{plan_id}",
        content=json.dumps(
            {
                "title": plan.title,
                "description": plan.description,
                "steps": getattr(plan, "steps", []) or [],
                "participants": getattr(plan, "participants", []) or [],
                "created_at": _safe_isoformat(getattr(plan, "created_at", None)),
                "updated_at": _safe_isoformat(getattr(plan, "updated_at", None)),
                "plan_id": plan_id,
            }
        ),
        metadata={
            "steps_count": len(getattr(plan, "steps", []) or []),
            "participants": getattr(plan, "participants", []) or [],
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
