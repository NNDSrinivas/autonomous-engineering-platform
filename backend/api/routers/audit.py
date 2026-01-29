"""
Audit and Replay API endpoints
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
import os
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, delete
from datetime import datetime, timedelta, timezone

from backend.core.db import get_db
from backend.core.auth.deps import require_role
from backend.core.auth.models import User, Role
from backend.core.eventstore.service import replay, get_plan_event_count
from backend.core.eventstore.models import AuditLog
from backend.core.audit_service.crypto import AuditEncryptionError, decrypt_payload
from backend.core.settings import settings

router = APIRouter(tags=["audit"])


class PlanEventOut(BaseModel):
    """Plan event response model"""

    seq: int
    type: str
    payload: dict
    by: str | None
    org_key: str | None
    created_at: str


@router.get("/plan/{plan_id}/replay", response_model=list[PlanEventOut])
def replay_plan_events(
    plan_id: str,
    since: Optional[int] = Query(
        None, ge=0, description="Replay events with seq > since"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.VIEWER)),
):
    """
    Replay plan events in chronological order.

    This endpoint allows reconstruction of plan state by replaying
    all events in sequence. Useful for debugging, auditing, and
    potentially implementing undo/redo functionality.

    Only returns events for plans in the user's organization.
    """
    try:
        # Security: Filter events by user's org at database level
        rows = replay(
            db, plan_id=plan_id, since_seq=since, limit=limit, org_key=user.org_id
        )

        # Convert to response format
        events = []
        for r in rows:
            events.append(
                {
                    "seq": r.seq,
                    "type": r.type,
                    "payload": r.payload,
                    "by": r.user_sub,
                    "org_key": r.org_key,
                    "created_at": r.created_at.isoformat(),
                }
            )

        return events
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to replay events: {str(e)}"
        )


class AuditOut(BaseModel):
    """Audit log response model"""

    id: int
    route: str
    method: str
    event_type: str
    org_key: str | None
    actor_sub: str | None
    actor_email: str | None
    resource_id: str | None
    status_code: int
    created_at: str


class AuditPurgeOut(BaseModel):
    """Audit purge response model"""

    deleted: int
    cutoff: str


class AuditPayloadOut(BaseModel):
    """Audit payload response model"""

    id: int
    encrypted: bool
    payload: dict


@router.get("/audit", response_model=list[AuditOut])
def list_audit_logs(
    org: Optional[str] = Query(None, description="Filter by organization key"),
    actor: Optional[str] = Query(None, description="Filter by actor subject"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    List audit logs for forensics and compliance.

    Admin-only endpoint that provides access to the audit trail
    for security analysis, compliance reporting, and debugging.
    """
    try:
        # Ensure audit table exists in test mode to avoid 500s
        if os.getenv("PYTEST_CURRENT_TEST"):
            AuditLog.__table__.create(bind=db.get_bind(), checkfirst=True)
        q = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)

        if org:
            q = q.where(AuditLog.org_key == org)
        if actor:
            q = q.where(AuditLog.actor_sub == actor)

        rows = db.execute(q).scalars().all()

        return [
            {
                "id": r.id,
                "route": r.route,
                "method": r.method,
                "event_type": r.event_type,
                "org_key": r.org_key,
                "actor_sub": r.actor_sub,
                "actor_email": r.actor_email,
                "resource_id": r.resource_id,
                "status_code": r.status_code,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve audit logs: {str(e)}"
        )


@router.post("/audit/purge", response_model=AuditPurgeOut)
def purge_audit_logs(
    days: Optional[int] = Query(
        None, ge=1, le=3650, description="Retention window in days"
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """
    Purge audit logs older than the retention window.

    Admin-only endpoint used for data retention enforcement.
    """
    if not settings.AUDIT_RETENTION_ENABLED:
        raise HTTPException(status_code=400, detail="Audit retention is disabled")

    retention_days = days or settings.AUDIT_RETENTION_DAYS
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)

    try:
        result = db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff_dt))
        db.commit()
        return {"deleted": result.rowcount or 0, "cutoff": cutoff_dt.isoformat()}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to purge audit logs: {str(e)}"
        )


@router.get("/audit/{audit_id}/payload", response_model=AuditPayloadOut)
def get_audit_payload(
    audit_id: int,
    decrypt: bool = Query(False, description="Return decrypted payload when available"),
    reason: Optional[str] = Query(
        None, max_length=256, description="Reason for decrypt access"
    ),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
):
    """
    Fetch an audit payload. Optionally decrypts when enabled.

    Admin-only endpoint for security/compliance review.
    """
    record = db.get(AuditLog, audit_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found")

    payload = record.payload or {}
    is_encrypted = bool(payload.get("encrypted"))

    if decrypt and is_encrypted:
        if not settings.AUDIT_ENCRYPTION_KEY:
            raise HTTPException(
                status_code=400, detail="Audit encryption key is not configured"
            )
        try:
            payload = decrypt_payload(payload, settings.AUDIT_ENCRYPTION_KEY)
        except AuditEncryptionError:
            raise HTTPException(status_code=400, detail="Audit payload decrypt failed")

        try:
            audit_record = AuditLog(
                org_key=user.org_id,
                actor_sub=user.user_id,
                actor_email=user.email,
                route=f"/api/audit/{audit_id}/payload",
                method="GET",
                event_type="audit.decrypt",
                resource_id=str(audit_id),
                payload={
                    "audit_id": audit_id,
                    "reason": reason,
                    "encrypted": True,
                },
                status_code=200,
            )
            db.add(audit_record)
            db.commit()
        except Exception:
            db.rollback()

    return {"id": record.id, "encrypted": is_encrypted, "payload": payload}


@router.get("/plan/{plan_id}/events/count")
def get_plan_events_count_endpoint(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.VIEWER)),
):
    """
    Get the total number of events for a plan.

    Only returns count for plans in the user's organization.
    """
    try:
        # Security: Verify plan belongs to user's org before returning count
        from backend.database.models.live_plan import LivePlan

        plan = (
            db.query(LivePlan)
            .filter(LivePlan.id == plan_id, LivePlan.org_id == user.org_id)
            .first()
        )

        if not plan:
            raise HTTPException(
                status_code=404, detail="Plan not found or not accessible"
            )

        count = get_plan_event_count(db, plan_id)
        return {"plan_id": plan_id, "event_count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get event count: {str(e)}"
        )
