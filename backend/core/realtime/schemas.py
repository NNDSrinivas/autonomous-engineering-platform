"""Pydantic schemas for real-time presence and cursor events."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PresenceJoin(BaseModel):
    user_id: str
    email: str
    org_id: str
    display_name: Optional[str] = None


class PresenceHeartbeat(BaseModel):
    user_id: str
    org_id: str


class PresenceLeave(BaseModel):
    user_id: str
    org_id: str


class PresenceEvent(BaseModel):
    type: str = Field(..., pattern=r"^(join|heartbeat|leave)$")
    plan_id: str
    user_id: str
    email: str
    org_id: str
    display_name: Optional[str] = None
    ts: int


class CursorEvent(BaseModel):
    plan_id: str
    user_id: str
    org_id: str
    x: float
    y: float
    ts: int
