"""
Organization onboarding API (selection + invites).

Lightweight tables are created on demand, similar to org_scan.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.core.auth.deps import require_role
from backend.core.auth.models import User, Role
from backend.core.settings import settings

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/orgs", tags=["org-onboarding"])

# Track if tables have been initialized (to avoid DDL on every request)
_tables_initialized = False
_tables_init_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


def _ensure_tables(db: Session) -> None:
    """Initialize org tables if not already done.

    TODO: Move to Alembic migrations for production.
    This on-demand creation is a development convenience but has issues:
    - Permissions: Requires DDL rights on every request
    - Concurrency: Race conditions with multiple requests
    - Performance: Overhead on every request (mitigated by flag)
    - Operations: Schema changes not tracked/versioned

    IMPORTANT: Only runs in development mode to avoid multi-worker DDL races.
    Production/staging deployments MUST use Alembic migrations instead.
    """
    global _tables_initialized

    # Check without lock first (fast path)
    if _tables_initialized:
        return

    # Acquire lock to prevent concurrent DDL operations
    with _tables_init_lock:
        # Double-check after acquiring lock
        if _tables_initialized:
            return

        # In production/staging, verify tables exist instead of creating them
        # This prevents multi-worker DDL race conditions and provides clear errors
        if settings.app_env in ("production", "staging"):
            logger.info(
                "[OrgOnboarding] Verifying tables exist in production/staging; "
                "tables must be managed via Alembic migrations."
            )
            # Verify required tables exist
            result = db.execute(
                text(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('navi_orgs', 'navi_org_members', 'navi_org_invites')
                    """
                )
            )
            existing_tables = {row[0] for row in result}
            required_tables = {"navi_orgs", "navi_org_members", "navi_org_invites"}
            missing_tables = required_tables - existing_tables

            if missing_tables:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Required tables missing in {settings.app_env} environment: {missing_tables}. "
                        "Run Alembic migrations to create them."
                    ),
                )

            _tables_initialized = True
            return

        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS navi_orgs (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  slug TEXT NOT NULL UNIQUE,
                  owner_user_id TEXT NOT NULL,
                  created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS navi_org_members (
                  org_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  created_at TIMESTAMP NOT NULL,
                  PRIMARY KEY (org_id, user_id)
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS navi_org_invites (
                  id TEXT PRIMARY KEY,
                  org_id TEXT NOT NULL,
                  email TEXT NOT NULL,
                  role TEXT NOT NULL,
                  invited_by TEXT NOT NULL,
                  created_at TIMESTAMP NOT NULL,
                  status TEXT NOT NULL
                )
                """
            )
        )
        db.commit()

        _tables_initialized = True


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    role: str


@router.get("", response_model=list[OrgOut])
def list_orgs(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.VIEWER)),
):
    _ensure_tables(db)
    rows = db.execute(
        text(
            """
            SELECT o.id, o.name, o.slug, m.role
            FROM navi_orgs o
            JOIN navi_org_members m ON m.org_id = o.id
            WHERE m.user_id = :user_id
            ORDER BY o.created_at DESC
            """
        ),
        {"user_id": user.user_id},
    ).fetchall()
    return [{"id": r[0], "name": r[1], "slug": r[2], "role": r[3]} for r in rows]


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    slug: Optional[str] = Field(None, min_length=2, max_length=80)


@router.post("", response_model=OrgOut)
def create_org(
    req: OrgCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.ADMIN)),
):
    _ensure_tables(db)
    org_id = uuid.uuid4().hex
    slug = _slugify(req.slug or req.name)

    # Ensure slug uniqueness
    existing = db.execute(
        text("SELECT id FROM navi_orgs WHERE slug = :slug"),
        {"slug": slug},
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Organization slug already exists")

    db.execute(
        text(
            """
            INSERT INTO navi_orgs (id, name, slug, owner_user_id, created_at)
            VALUES (:id, :name, :slug, :owner_user_id, :created_at)
            """
        ),
        {
            "id": org_id,
            "name": req.name,
            "slug": slug,
            "owner_user_id": user.user_id,
            "created_at": _now(),
        },
    )
    db.execute(
        text(
            """
            INSERT INTO navi_org_members (org_id, user_id, role, created_at)
            VALUES (:org_id, :user_id, :role, :created_at)
            ON CONFLICT (org_id, user_id) DO NOTHING
            """
        ),
        {
            "org_id": org_id,
            "user_id": user.user_id,
            "role": "owner",
            "created_at": _now(),
        },
    )
    db.commit()
    return {"id": org_id, "name": req.name, "slug": slug, "role": "owner"}


class OrgSelectRequest(BaseModel):
    org_id: str


@router.post("/select")
def select_org(
    req: OrgSelectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.VIEWER)),
):
    _ensure_tables(db)
    row = db.execute(
        text(
            """
            SELECT 1
            FROM navi_org_members
            WHERE org_id = :org_id AND user_id = :user_id
            """
        ),
        {"org_id": req.org_id, "user_id": user.user_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="User not in organization")
    return {"org_id": req.org_id}


# Allowed roles for invitations
ALLOWED_INVITE_ROLES = {"member", "viewer", "admin"}


class OrgInviteRequest(BaseModel):
    org_id: str
    emails: list[str] = Field(..., min_length=1)
    role: str = Field(default="member")


@router.post("/invite")
def invite_users(
    req: OrgInviteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.VIEWER)),
):
    _ensure_tables(db)

    # Validate role against allowlist
    if req.role not in ALLOWED_INVITE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Allowed roles: {', '.join(sorted(ALLOWED_INVITE_ROLES))}",
        )

    # Check inviter is owner or admin (not just any member)
    row = db.execute(
        text(
            """
            SELECT role FROM navi_org_members
            WHERE org_id = :org_id AND user_id = :user_id
            """
        ),
        {"org_id": req.org_id, "user_id": user.user_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="User not in organization")

    inviter_role = row[0]
    if inviter_role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403, detail="Only owners and admins can invite users"
        )

    invites = []
    for email in req.emails:
        invite_id = uuid.uuid4().hex
        db.execute(
            text(
                """
                INSERT INTO navi_org_invites (id, org_id, email, role, invited_by, created_at, status)
                VALUES (:id, :org_id, :email, :role, :invited_by, :created_at, :status)
                """
            ),
            {
                "id": invite_id,
                "org_id": req.org_id,
                "email": email.strip().lower(),
                "role": req.role,
                "invited_by": user.user_id,
                "created_at": _now(),
                "status": "pending",
            },
        )
        invites.append(
            {"id": invite_id, "email": email.strip().lower(), "role": req.role}
        )
    db.commit()
    return {"invited": invites}
