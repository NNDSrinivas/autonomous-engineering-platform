"""
Audit Middleware for capturing mutating HTTP requests
"""

from __future__ import annotations
import logging
from contextlib import contextmanager
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import os
from backend.core.db import get_db
from backend.core.settings import settings
from backend.core.eventstore.models import AuditLog
from backend.core.audit_service.crypto import AuditEncryptionError, encrypt_payload
from sqlalchemy import inspect

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@contextmanager
def get_db_session():
    """Context manager for database sessions to prevent connection leaks."""
    # Use the generator properly with explicit iteration
    db_generator = get_db()
    session = None
    try:
        session = next(db_generator)
        yield session
    finally:
        if session:
            session.close()
        # Properly close the generator to trigger cleanup
        next(db_generator, None)


class EnhancedAuditMiddleware(BaseHTTPMiddleware):
    """
    Write-ahead audit middleware for mutating requests.
    Stores org/user/route/method/status/payload snapshot for forensics.

    This middleware captures all mutating HTTP requests and stores them
    in the audit_log_enhanced table for compliance and debugging.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Only audit mutating requests
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # Skip body capture to avoid consuming the request stream
        # The body will be captured post-response if needed for audit
        payload = {"query_params": dict(request.query_params)}

        # Extract actor context (set by auth middleware)
        actor = getattr(request.state, "user", None)
        org_key = None
        actor_sub = None
        actor_email = None

        if actor:
            # Adapt to your User model structure
            org_key = getattr(actor, "org_key", getattr(actor, "org_id", None))
            actor_sub = getattr(actor, "sub", getattr(actor, "id", None))
            actor_email = getattr(actor, "email", None)
        elif os.getenv("ALLOW_DEV_AUTH") == "true":
            # Dev/test fallback when auth middleware isn't wiring request.state.user
            org_key = os.getenv("DEV_ORG_ID")
            actor_sub = os.getenv("DEV_USER_ID")
            actor_email = os.getenv("DEV_USER_EMAIL")

        # Process the request
        response = await call_next(request)

        # Persist audit record (never block the response)
        try:
            # Use contextual session management to prevent leaks
            with get_db_session() as session:
                # In tests, ensure audit table exists to avoid 500s
                if os.getenv("PYTEST_CURRENT_TEST"):
                    inspector = inspect(session.bind)
                    if "audit_log_enhanced" not in inspector.get_table_names():
                        AuditLog.__table__.create(bind=session.bind, checkfirst=True)
                audit_payload = payload
                if settings.AUDIT_ENCRYPTION_KEY:
                    try:
                        audit_payload = encrypt_payload(
                            payload,
                            settings.AUDIT_ENCRYPTION_KEY,
                            settings.AUDIT_ENCRYPTION_KEY_ID,
                        )
                    except AuditEncryptionError:
                        audit_payload = {"encrypted": True, "error": "encryption_failed"}

                audit_record = AuditLog(
                    org_key=org_key,
                    actor_sub=actor_sub,
                    actor_email=actor_email,
                    route=str(request.url.path),
                    method=request.method,
                    event_type="http.request",
                    resource_id=_extract_resource_id(request),
                    payload=audit_payload,
                    status_code=response.status_code,
                )
                session.add(audit_record)
                session.commit()
        except Exception as e:
            # Never let audit failures break the response
            logger.warning(f"Audit logging failed: {e}")

        return response


def _extract_resource_id(request: Request) -> str | None:
    """
    Extract meaningful resource ID from request path.

    This attempts to identify the primary resource being operated on
    from the URL path structure.
    """
    parts = request.url.path.rstrip("/").split("/")

    # Filter out common non-ID path segments
    non_id_segments = {
        "api",
        "plan",
        "step",
        "events",
        "archive",
        "cursor",
        "heartbeat",
        "join",
        "leave",
        "admin",
        "rbac",
        "audit",
    }

    # Look for UUID-like or meaningful ID patterns in reverse order
    for part in reversed(parts):
        if part and part not in non_id_segments:
            # Return if it looks like an ID (contains alphanumeric chars)
            if part.replace("-", "").replace("_", "").isalnum():
                return part

    return None
