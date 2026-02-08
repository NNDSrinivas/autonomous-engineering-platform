"""
Audit and Replay API endpoints
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime, timezone
import csv
import io
import json
import os
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from backend.core.db import get_db
from backend.core.auth.deps import require_role
from backend.core.auth.models import User, Role
from backend.core.eventstore.service import replay, get_plan_event_count
from backend.core.eventstore.models import AuditLog
from backend.core.crypto import decrypt_audit_payload, AuditEncryptionError

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


class AuditDecryptRequest(BaseModel):
    reason: Optional[str] = None


class AuditDecryptOut(BaseModel):
    id: int
    payload: dict
    key_id: Optional[str] = None


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


@router.get("/audit/export")
def export_audit_logs(
    export_format: str = Query("json", pattern="^(json|csv)$"),
    org: Optional[str] = Query(None, description="Filter by organization key"),
    actor: Optional[str] = Query(None, description="Filter by actor subject"),
    since: Optional[str] = Query(None, description="ISO timestamp (inclusive)"),
    until: Optional[str] = Query(None, description="ISO timestamp (inclusive)"),
    include_payload: bool = Query(False, description="Include raw payload data"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """
    Export audit logs as JSON or CSV for compliance tooling.

    Security: Exports are scoped to the caller's organization by default.
    Cross-org export requires elevated privileges (future: SUPERADMIN role).
    """
    try:
        # Get caller's organization context
        user_org = getattr(current_user, "org_key", None) or getattr(
            current_user, "org_id", None
        )
        if not user_org:
            raise HTTPException(
                status_code=500,
                detail="User missing organization context - cannot scope audit export",
            )

        # Check if user has super-admin privileges (cross-org export)
        # For now, all admins are org-scoped. Future: add SUPERADMIN role.
        is_super_admin = False

        # Enforce org scoping: admins can only export their own org's logs
        if org and org != user_org and not is_super_admin:
            raise HTTPException(
                status_code=403, detail="Cross-organization audit export not permitted"
            )

        # Use caller's org if not specified, or validate if specified
        effective_org = org if (org and is_super_admin) else user_org

        if os.getenv("PYTEST_CURRENT_TEST"):
            AuditLog.__table__.create(bind=db.get_bind(), checkfirst=True)

        # Always filter by organization for security
        q = (
            select(AuditLog)
            .where(AuditLog.org_key == effective_org)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        if actor:
            q = q.where(AuditLog.actor_sub == actor)
        if since:
            q = q.where(AuditLog.created_at >= _parse_iso_time(since))
        if until:
            q = q.where(AuditLog.created_at <= _parse_iso_time(until))

        rows = db.execute(q).scalars().all()

        if export_format == "json":
            return [
                _audit_row_to_dict(row, include_payload=include_payload) for row in rows
            ]

        output = io.StringIO()
        fieldnames = [
            "id",
            "route",
            "method",
            "event_type",
            "org_key",
            "actor_sub",
            "actor_email",
            "resource_id",
            "status_code",
            "created_at",
        ]
        if include_payload:
            fieldnames.append("payload")

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row_dict = _audit_row_to_dict(row, include_payload=include_payload)
            # JSON-encode payload to prevent CSV corruption from nested dicts/lists
            # Always serialize non-string payloads to ensure consistent format
            if (
                include_payload
                and "payload" in row_dict
                and row_dict["payload"] is not None
            ):
                if not isinstance(row_dict["payload"], str):
                    # Handle bytes (common for encrypted payloads) and other non-JSON types
                    if isinstance(row_dict["payload"], bytes):
                        import base64

                        row_dict["payload"] = base64.b64encode(
                            row_dict["payload"]
                        ).decode("utf-8")
                    else:
                        # Use default=str to handle any non-JSON-serializable types
                        row_dict["payload"] = json.dumps(
                            row_dict["payload"], default=str
                        )
            writer.writerow(row_dict)

        return PlainTextResponse(output.getvalue(), media_type="text/csv")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to export audit logs: {str(e)}"
        )


def _parse_iso_time(value: str) -> datetime:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        # Ensure timezone-aware datetime (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc


def _audit_row_to_dict(row: AuditLog, include_payload: bool = False) -> dict:
    # Handle naive datetimes by assuming UTC when tzinfo is None
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    data = {
        "id": row.id,
        "route": row.route,
        "method": row.method,
        "event_type": row.event_type,
        "org_key": row.org_key,
        "actor_sub": row.actor_sub,
        "actor_email": row.actor_email,
        "resource_id": row.resource_id,
        "status_code": row.status_code,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
    }
    if include_payload:
        # Serialize payload safely for JSON export (handle bytes and other non-JSON types)
        if isinstance(row.payload, bytes):
            import base64

            data["payload"] = base64.b64encode(row.payload).decode("utf-8")
            data["payload_encoding"] = "base64"
        elif row.payload is None:
            data["payload"] = None
        else:
            # For dicts/lists/other JSON-serializable types, return native object
            # This avoids forcing consumers to double-parse JSON strings
            try:
                json.dumps(row.payload)  # Validate serializability
                data["payload"] = row.payload  # Return as-is
            except (TypeError, ValueError):
                # Fallback: convert to string for non-serializable types
                data["payload"] = str(row.payload)
    return data


@router.post("/audit/{audit_id}/decrypt", response_model=AuditDecryptOut)
def decrypt_audit_log(
    audit_id: int,
    req: AuditDecryptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
):
    """
    Decrypt an audit payload for authorized admin review.
    """
    row = db.get(AuditLog, audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit log not found")
    if row.org_key and user.org_id and row.org_key != user.org_id:
        raise HTTPException(status_code=404, detail="Audit log not found")

    try:
        payload = decrypt_audit_payload(row.payload)
    except AuditEncryptionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    key_id = None
    if isinstance(row.payload, dict):
        key_id = row.payload.get("key_id")

    return {"id": row.id, "payload": payload, "key_id": key_id}


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
