from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.core.db import get_db
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional

router = APIRouter(prefix="/api/changes", tags=["changes"])


def _current_user_id(user) -> str:
    return getattr(user, "user_id", None) or "default_user"


@router.get("/recent")
def recent_changes(
    limit: int = 10,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    rows = (
        db.execute(
            text(
                """
                SELECT id, summary, details, created_at
                FROM change_set
                WHERE (:org_id IS NULL OR org_id = :org_id)
                  AND user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"org_id": org_id, "user_id": user_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return {"items": [dict(r) for r in rows]}


@router.get("/{change_id}")
def get_change(
    change_id: int,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    row = (
        db.execute(
            text(
                """
                SELECT id, summary, details, created_at
                FROM change_set
                WHERE id = :change_id
                  AND (:org_id IS NULL OR org_id = :org_id)
                  AND user_id = :user_id
                """
            ),
            {"change_id": change_id, "org_id": org_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Change set not found")
    return dict(row)


@router.get("/{change_id}/diff")
def get_change_diff(
    change_id: int,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    row = (
        db.execute(
            text(
                """
                SELECT details
                FROM change_set
                WHERE id = :change_id
                  AND (:org_id IS NULL OR org_id = :org_id)
                  AND user_id = :user_id
                """
            ),
            {"change_id": change_id, "org_id": org_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Change set not found")
    details = row.get("details") or {}
    patch = details.get("patch")
    if not patch:
        raise HTTPException(
            status_code=404, detail="No diff stored for this change set"
        )
    return {"patch": patch}


@router.post("/undo/{change_id}")
def undo_change(
    change_id: int,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    org_id = org_ctx.get("org_id")
    user_id = _current_user_id(user)
    row = (
        db.execute(
            text(
                """
                SELECT details
                FROM change_set
                WHERE id = :change_id
                  AND (:org_id IS NULL OR org_id = :org_id)
                  AND user_id = :user_id
                """
            ),
            {"change_id": change_id, "org_id": org_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Change set not found")

    details = row.get("details") or {}
    patch = details.get("patch")
    workspace_root = details.get("workspace_root")
    if not patch:
        raise HTTPException(
            status_code=400, detail="No patch stored for this change set"
        )
    if not workspace_root:
        raise HTTPException(status_code=400, detail="Missing workspace path for undo")

    # Apply reverse patch using git apply -R
    try:
        import subprocess

        proc = subprocess.run(
            ["git", "apply", "-R", "-"],
            input=patch,
            text=True,
            capture_output=True,
            cwd=workspace_root,
            check=False,
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Undo failed: {proc.stderr or proc.stdout or 'git apply error'}",
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logging.error("Undo operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Undo operation failed")

    return {"ok": True, "message": "Changes undone via stored patch."}
