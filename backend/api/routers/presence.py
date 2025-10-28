"""API endpoints for presence tracking and cursor synchronization."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.deps import get_broadcaster
from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.core.realtime.presence import (
    cursor_channel,
    note_heartbeat,
    presence_channel,
)
from backend.core.realtime.schemas import (
    CursorEvent,
    PresenceEvent,
    PresenceHeartbeat,
    PresenceJoin,
    PresenceLeave,
)
from backend.infra.broadcast.base import Broadcast

router = APIRouter(prefix="/api/plan", tags=["presence"])


@router.post("/{plan_id}/presence/join")
async def presence_join(
    plan_id: str,
    body: PresenceJoin,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
):
    """User joins a plan - broadcast presence event and start TTL tracking."""
    note_heartbeat(plan_id, body.user_id)
    evt = PresenceEvent(
        type="join",
        plan_id=plan_id,
        user_id=body.user_id,
        email=body.email,
        org_id=body.org_id,
        display_name=body.display_name,
        ts=int(time.time()),
    )
    await bc.publish(presence_channel(plan_id), evt.json())
    return {"ok": True}


@router.post("/{plan_id}/presence/heartbeat")
async def presence_heartbeat(
    plan_id: str,
    body: PresenceHeartbeat,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
):
    """Periodic heartbeat to maintain presence - updates TTL."""
    note_heartbeat(plan_id, body.user_id)
    evt = PresenceEvent(
        type="heartbeat",
        plan_id=plan_id,
        user_id=body.user_id,
        email=user.email or "",
        org_id=body.org_id,
        ts=int(time.time()),
    )
    await bc.publish(presence_channel(plan_id), evt.json())
    return {"ok": True}


@router.post("/{plan_id}/presence/leave")
async def presence_leave(
    plan_id: str,
    body: PresenceLeave,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
):
    """User leaves a plan - broadcast leave event."""
    evt = PresenceEvent(
        type="leave",
        plan_id=plan_id,
        user_id=body.user_id,
        email=user.email or "",
        org_id=body.org_id,
        ts=int(time.time()),
    )
    await bc.publish(presence_channel(plan_id), evt.json())
    return {"ok": True}


@router.post("/{plan_id}/cursor")
async def cursor_update(
    plan_id: str,
    body: CursorEvent,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
):
    """Broadcast cursor position update to other clients."""
    payload = body.copy(update={"ts": int(time.time())})
    await bc.publish(cursor_channel(plan_id), payload.json())
    return {"ok": True}
