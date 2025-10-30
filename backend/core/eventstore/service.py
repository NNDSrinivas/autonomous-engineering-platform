"""
Event Store Service for appending and replaying plan events
"""

from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from .models import PlanEvent


def next_seq(session: Session, plan_id: str) -> int:
    """Get the next sequence number for a plan, using PostgreSQL advisory locks for proper concurrency control."""
    import hashlib

    # Use PostgreSQL advisory lock based on plan_id hash for proper serialization
    # This ensures even the first insert for a new plan is properly serialized
    plan_hash = int(hashlib.md5(plan_id.encode()).hexdigest()[:8], 16)

    # Acquire advisory lock for this plan_id (automatically released at transaction end)
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": plan_hash}
    )

    # Now safely get the max sequence number
    last = session.execute(
        select(func.max(PlanEvent.seq)).where(PlanEvent.plan_id == plan_id)
    ).scalar()
    return 1 if last is None else int(last) + 1


def append_event(
    session: Session,
    *,
    plan_id: str,
    type: str,
    payload: dict,
    user_sub: str | None,
    org_key: str | None,
) -> PlanEvent:
    """
    Append a new event to the plan's event log with monotonic sequence number.

    Args:
        session: Database session
        plan_id: Plan identifier
        type: Event type (e.g., 'step', 'note', 'archive')
        payload: Event payload data
        user_sub: User subject who triggered the event
        org_key: Organization key for the event

    Returns:
        The created PlanEvent
    """
    seq = next_seq(session, plan_id)
    evt = PlanEvent(
        plan_id=plan_id,
        seq=seq,
        type=type,
        payload=payload,
        user_sub=user_sub,
        org_key=org_key,
    )
    session.add(evt)
    session.flush()  # Get the ID immediately
    return evt


def replay(
    session: Session,
    *,
    plan_id: str,
    since_seq: int | None = None,
    limit: int = 500,
) -> list[PlanEvent]:
    """
    Replay events for a plan in sequence order.

    Args:
        session: Database session
        plan_id: Plan identifier
        since_seq: Only return events with seq > since_seq
        limit: Maximum number of events to return

    Returns:
        List of PlanEvent objects in sequence order
    """
    q = select(PlanEvent).where(PlanEvent.plan_id == plan_id)
    if since_seq is not None:
        q = q.where(PlanEvent.seq > since_seq)
    q = q.order_by(PlanEvent.seq.asc()).limit(limit)
    rows = session.execute(q).scalars().all()
    return list(rows)


def get_plan_event_count(session: Session, plan_id: str) -> int:
    """Get the total number of events for a plan"""
    count = session.execute(
        select(func.count(PlanEvent.id)).where(PlanEvent.plan_id == plan_id)
    ).scalar()
    return count or 0
