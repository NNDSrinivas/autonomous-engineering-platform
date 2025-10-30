"""
Publisher: append events to store and broadcast via Redis
"""
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend.core.eventstore.service import append_event
from backend.core.settings import settings


async def append_and_broadcast(
    session: Session,
    *,
    bc,  # Broadcast instance
    plan_id: str,
    type: str,
    payload: dict,
    user_sub: str | None,
    org_key: str | None,
):
    """
    Append event to persistent store and broadcast via Redis.
    
    This is the main entry point for plan events - it ensures durability
    while maintaining real-time capabilities.
    
    Args:
        session: Database session for persistence
        bc: Broadcast instance for Redis publishing
        plan_id: Plan identifier
        type: Event type (e.g., 'step', 'note', 'archive')
        payload: Event data
        user_sub: User who triggered the event
        org_key: Organization context
        
    Returns:
        The created PlanEvent with sequence number
    """
    # First, persist to database with monotonic sequence
    evt = append_event(
        session,
        plan_id=plan_id,
        type=type,
        payload=payload,
        user_sub=user_sub,
        org_key=org_key,
    )
    
    # Then broadcast to Redis for real-time updates
    channel = f"{settings.PLAN_CHANNEL_PREFIX}{plan_id}"
    await bc.publish(
        channel,
        json.dumps({
            "type": type,
            "seq": evt.seq,
            "plan_id": plan_id,
            "payload": payload,
            "by": user_sub,
            "org_key": org_key,
            "timestamp": evt.created_at.isoformat(),
        })
    )
    
    return evt