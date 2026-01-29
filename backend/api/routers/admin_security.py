"""Admin security status endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.core.settings import settings
from backend.core.eventstore.models import AuditLog
from backend.database.session import get_db
from backend.core.auth0 import AUTH0_CLIENT_ID, AUTH0_AUDIENCE, AUTH0_DOMAIN


router = APIRouter(prefix="/api/admin/security", tags=["admin-security"])


class AuditRetentionStatus(BaseModel):
    enabled: bool
    retention_days: int
    overdue_count: int
    cutoff_iso: str


class JwtStatus(BaseModel):
    enabled: bool
    has_primary_secret: bool
    has_previous_secrets: bool
    rotation_ready: bool


class EncryptionStatus(BaseModel):
    audit_encryption_enabled: bool
    audit_encryption_key_id: Optional[str]
    token_encryption_configured: bool
    token_encryption_key_id: Optional[str]


class SsoStatus(BaseModel):
    auth0_domain: str
    auth0_client_configured: bool
    auth0_audience_configured: bool
    device_flow_enabled: bool


class SecurityStatus(BaseModel):
    jwt: JwtStatus
    encryption: EncryptionStatus
    audit_retention: AuditRetentionStatus
    sso: SsoStatus


@router.get("/status", response_model=SecurityStatus)
def get_security_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
):
    """Return an enterprise security posture snapshot for admins."""
    # Audit retention snapshot
    retention_days = settings.AUDIT_RETENTION_DAYS
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
    overdue_count = 0
    if settings.AUDIT_RETENTION_ENABLED:
        try:
            overdue_count = (
                db.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.created_at < cutoff_dt)
                )
                .scalars()
                .first()
                or 0
            )
        except Exception:
            overdue_count = 0

    jwt_status = JwtStatus(
        enabled=settings.JWT_ENABLED,
        has_primary_secret=bool(settings.JWT_SECRET),
        has_previous_secrets=bool(settings.JWT_SECRET_PREVIOUS),
        rotation_ready=bool(settings.JWT_SECRET and settings.JWT_SECRET_PREVIOUS),
    )

    token_key_id = os.environ.get("TOKEN_ENCRYPTION_KEY_ID")
    encryption_status = EncryptionStatus(
        audit_encryption_enabled=bool(settings.AUDIT_ENCRYPTION_KEY),
        audit_encryption_key_id=(
            settings.AUDIT_ENCRYPTION_KEY_ID if settings.AUDIT_ENCRYPTION_KEY else None
        ),
        token_encryption_configured=bool(token_key_id),
        token_encryption_key_id=token_key_id if token_key_id else None,
    )

    sso_status = SsoStatus(
        auth0_domain=AUTH0_DOMAIN,
        auth0_client_configured=bool(AUTH0_CLIENT_ID),
        auth0_audience_configured=bool(AUTH0_AUDIENCE),
        device_flow_enabled=bool(AUTH0_CLIENT_ID and AUTH0_AUDIENCE),
    )

    audit_retention_status = AuditRetentionStatus(
        enabled=settings.AUDIT_RETENTION_ENABLED,
        retention_days=retention_days,
        overdue_count=overdue_count,
        cutoff_iso=cutoff_dt.isoformat(),
    )

    return SecurityStatus(
        jwt=jwt_status,
        encryption=encryption_status,
        audit_retention=audit_retention_status,
        sso=sso_status,
    )
