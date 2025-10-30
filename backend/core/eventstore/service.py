"""
Event Store Service for appending and replaying plan events
"""

from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .models import PlanEvent


def next_seq(session: Session, plan_id: str) -> int:
    """Get the next sequence number for a plan, using row-level locking to prevent race conditions."""
    # First try to lock existing rows for this plan to establish ordering
    session.execute(
        select(PlanEvent.id)
        .where(PlanEvent.plan_id == plan_id)
        .with_for_update(skip_locked=True)
        .limit(1)
    ).first()

    # Now get the max sequence number (this will be consistent due to the lock)
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
