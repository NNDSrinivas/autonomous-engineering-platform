"""
Event Store Models for Audit and Plan Event Replay
"""

from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, JSON, Index
from datetime import datetime, timezone
from backend.core.db import Base


def utcnow() -> datetime:
    """Get current UTC timestamp"""
    return datetime.now(tz=timezone.utc)


class PlanEvent(Base):
    """
    Append-only event log per plan for replay functionality.
    Each plan has its own sequence of events with monotonic sequence numbers.
    """

    __tablename__ = "plan_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(
        Integer, index=True, nullable=False
    )  # monotonic per plan
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    user_sub: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    org_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    __table_args__ = (
        # Ensure monotonic uniqueness per plan
        Index("ix_events_plan_seq", "plan_id", "seq", unique=True),
    )


class AuditLog(Base):
    """
    Enhanced audit trail for security and forensics.
    Extends the existing audit_log table with additional fields.
    """

    __tablename__ = "audit_log_enhanced"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_key: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )
    actor_sub: Mapped[Optional[str]] = mapped_column(
        String(128), index=True, nullable=True
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )  # e.g., plan_id
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_enhanced_org_created", "org_key", "created_at"),
        Index("ix_audit_enhanced_actor_created", "actor_sub", "created_at"),
    )
