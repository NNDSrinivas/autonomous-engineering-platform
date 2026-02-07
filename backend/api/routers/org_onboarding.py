"""
Organization onboarding API (selection + invites).

Lightweight tables are created on demand, similar to org_scan.
"""

from __future__ import annotations

import re
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


router = APIRouter(prefix="/api/orgs", tags=["org-onboarding"])


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


def _ensure_tables(db: Session) -> None:
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
    user: User = Depends(require_role(Role.VIEWER)),
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


class OrgInviteRequest(BaseModel):
    org_id: str
    emails: list[str] = Field(..., min_items=1)
    role: str = Field(default="member")


@router.post("/invite")
def invite_users(
    req: OrgInviteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.VIEWER)),
):
    _ensure_tables(db)
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
