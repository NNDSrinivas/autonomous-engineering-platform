"""API endpoints for presence tracking and cursor synchronization."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status

from backend.api.deps import get_broadcaster
from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.core.realtime_engine.presence import (
    cursor_channel,
    note_org_heartbeat,
    note_heartbeat,
    presence_channel,
    remove_org_user,
)
from backend.core.realtime_engine.schemas import (
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
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """User joins a plan - broadcast presence event and start TTL tracking."""
    # SECURITY: Validate that client cannot impersonate other users or orgs
    if body.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot join as a different user",
        )
    # Validate org consistency between body and header
    # Note: user.org_id is derived from X-Org-Id header in dev mode
    if body.org_id != x_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization ID mismatch",
        )

    note_heartbeat(plan_id, user.user_id)
    note_org_heartbeat(x_org_id, user.user_id)
    evt = PresenceEvent(
        type="join",
        plan_id=plan_id,
        user_id=user.user_id,
        email=user.email or body.email,
        org_id=x_org_id,
        display_name=body.display_name or user.display_name,
        ts=int(time.time()),
    )
    await bc.publish(presence_channel(plan_id), evt.model_dump_json())
    return {"ok": True}


@router.post("/{plan_id}/presence/heartbeat")
async def presence_heartbeat(
    plan_id: str,
    body: PresenceHeartbeat,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """Periodic heartbeat to maintain presence - updates TTL."""
    # SECURITY: Validate that client cannot send heartbeat for other users
    if body.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot send heartbeat as a different user",
        )
    # Validate org consistency between body and header
    # Note: user.org_id is derived from X-Org-Id header in dev mode
    if body.org_id != x_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization ID mismatch",
        )

    note_heartbeat(plan_id, user.user_id)
    note_org_heartbeat(x_org_id, user.user_id)
    evt = PresenceEvent(
        type="heartbeat",
        plan_id=plan_id,
        user_id=user.user_id,
        email=user.email or "",
        org_id=x_org_id,
        ts=int(time.time()),
    )
    await bc.publish(presence_channel(plan_id), evt.model_dump_json())
    return {"ok": True}


@router.post("/{plan_id}/presence/leave")
async def presence_leave(
    plan_id: str,
    body: PresenceLeave,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """User leaves a plan - broadcast leave event."""
    # SECURITY: Validate that client cannot send leave for other users
    if body.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot leave as a different user",
        )
    # Validate org consistency between body and header
    # Note: user.org_id is derived from X-Org-Id header in dev mode
    if body.org_id != x_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization ID mismatch",
        )

    evt = PresenceEvent(
        type="leave",
        plan_id=plan_id,
        user_id=user.user_id,
        email=user.email or "",
        org_id=x_org_id,
        ts=int(time.time()),
    )
    remove_org_user(x_org_id, user.user_id)
    await bc.publish(presence_channel(plan_id), evt.model_dump_json())
    return {"ok": True}


@router.post("/{plan_id}/cursor")
async def cursor_update(
    plan_id: str,
    body: CursorEvent,
    user: Annotated[User, Depends(require_role(Role.VIEWER))],
    bc: Annotated[Broadcast, Depends(get_broadcaster)],
    x_org_id: str = Header(..., alias="X-Org-Id"),
):
    """Broadcast cursor position update to other clients."""
    # SECURITY: Validate that client cannot send cursor updates for other users
    if body.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot send cursor update as a different user",
        )
    # Validate org consistency between body and header
    # Note: user.org_id is derived from X-Org-Id header in dev mode
    if body.org_id != x_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization ID mismatch",
        )
    # Validate plan_id consistency between path and body
    if body.plan_id != plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan ID mismatch between path and body",
        )

    # Use Pydantic v2 model_copy to override ts with server timestamp
    # This ensures server-controlled timestamp regardless of client value
    payload = body.model_copy(update={"ts": int(time.time())})
    await bc.publish(cursor_channel(plan_id), payload.model_dump_json())
    return {"ok": True}
