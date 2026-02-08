from __future__ import annotations

import os
import subprocess
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.core.db import get_db
from backend.core.auth.deps import get_current_user_optional
from backend.services.command_utils import (
    compute_timeout,
    format_command_message,
    get_command_env,
    get_shell_executable,
    prepare_command,
    run_subprocess,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/run", tags=["command-runner"])


class RunRequest(BaseModel):
    command: str = Field(..., description="Command to run (exact string)")
    workdir: Optional[str] = Field(
        None, description="Working directory to run the command in"
    )
    approved: bool = Field(False, description="Must be true to actually execute")
    background: bool = Field(
        False, description="If true, start command in background and return immediately"
    )


class RunResponse(BaseModel):
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    message: Optional[str] = None
    audit_id: Optional[str] = None


_ALLOWLIST: List[str] = [
    "npm install",
    "npm run dev",
    "npm install && npm run dev",
    "npm test",
    "npm run test",
    "npm run build",
    "npm run lint",
    "npm run start",
    "npm ci",
    "yarn install",
    "yarn run dev",
    "yarn run build",
    "yarn run start",
    "pnpm install",
    "pnpm run dev",
    "pnpm run build",
    "pnpm run start",
    "node -v",
    "npm -v",
    "python3 --version",
    "pip --version",
    "pip install -r requirements.txt",
    "pip install -e .",
    "pytest",
    "docker compose up -d",
    "docker-compose up -d",
]
_AUTO_APPROVE: List[str] = []


def _ensure_table(db) -> None:
    try:
        # Detect dialect to use appropriate timestamp type
        dialect = getattr(getattr(db.bind, "dialect", None), "dialect", None)
        dialect_name = getattr(dialect, "name", "") if dialect else ""

        timestamp_type = "TEXT" if dialect_name == "sqlite" else "TIMESTAMPTZ"
        default_timestamp = (
            "CURRENT_TIMESTAMP" if dialect_name == "sqlite" else "CURRENT_TIMESTAMP"
        )

        db.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS navi_run_allowlist (
                    command TEXT PRIMARY KEY,
                    auto_approve {'INTEGER' if dialect_name == 'sqlite' else 'BOOLEAN'} DEFAULT {'0' if dialect_name == 'sqlite' else 'FALSE'},
                    updated_at {timestamp_type} DEFAULT {default_timestamp}
                )
                """
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _is_allowlisted(cmd: str) -> bool:
    # Exact or prefix match for simple allowlist entries
    for allowed in _ALLOWLIST:
        if cmd == allowed:
            return True
        # Allow args after the allowed prefix
        if cmd.startswith(allowed + " "):
            return True
    return False


@router.get("/config")
def get_allowlist(db=Depends(get_db)):
    """Return current allowlist and auto-approve list."""
    _ensure_table(db)
    rows = (
        db.execute(
            text(
                "SELECT command, auto_approve FROM navi_run_allowlist ORDER BY command"
            )
        )
        .mappings()
        .all()
    )
    commands = [dict(r) for r in rows] if rows else []
    if not commands:
        # Seed defaults
        commands = [{"command": c, "auto_approve": False} for c in _ALLOWLIST]
    auto = [c["command"] for c in commands if c.get("auto_approve")]
    return {"commands": commands, "auto_approve": auto}


class AllowlistUpdate(BaseModel):
    commands: List[str]
    auto_approve: List[str] = []


@router.post("/config")
def update_allowlist(body: AllowlistUpdate, db=Depends(get_db)):
    """Replace allowlist with provided commands and auto-approve subset."""
    _ensure_table(db)
    try:
        db.execute(text("DELETE FROM navi_run_allowlist"))
        for cmd in body.commands:
            db.execute(
                text(
                    "INSERT INTO navi_run_allowlist (command, auto_approve) VALUES (:c, :aa)"
                ),
                {"c": cmd.strip(), "aa": cmd.strip() in set(body.auto_approve)},
            )
        db.commit()
        return {"ok": True, "count": len(body.commands)}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("[CMD] Failed to update allowlist: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update allowlist")


@router.post("", response_model=RunResponse)
def run_command(
    req: RunRequest,
    db=Depends(get_db),
    user=Depends(get_current_user_optional),
):
    """
    Approval-gated command runner. Only runs allowlisted commands and only when approved=true.
    """
    user_id = getattr(user, "user_id", None) or "default_user"

    if not req.approved:
        raise HTTPException(status_code=403, detail="Approval required to run commands")

    cmd = (req.command or "").strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="command is required")

    # Reload allowlist from DB if present
    _ensure_table(db)
    rows = (
        db.execute(text("SELECT command, auto_approve FROM navi_run_allowlist"))
        .mappings()
        .all()
    )
    allow_from_db = [r["command"] for r in rows] if rows else _ALLOWLIST
    [r["command"] for r in rows if r.get("auto_approve")] if rows else _AUTO_APPROVE

    if not any(
        cmd == allowed or cmd.startswith(allowed + " ") for allowed in allow_from_db
    ):
        raise HTTPException(status_code=403, detail="Command not allowlisted")

    # Normalize workdir
    workdir = req.workdir or os.getcwd()
    if not os.path.isdir(workdir):
        raise HTTPException(status_code=400, detail=f"Invalid workdir: {workdir}")

    # Run command securely
    try:
        audit_id = f"{user_id}-{datetime.now(timezone.utc).isoformat()}"

        # Prepare environment and command with node setup if needed
        timeout = compute_timeout(cmd, timeout=300)

        # Background mode for long-running servers (e.g., npm run dev)
        if req.background:
            prepared_cmd = prepare_command(cmd, workdir)
            proc = subprocess.Popen(
                prepared_cmd,
                shell=True,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,  # detach from parent
                env=get_command_env(),
                executable=get_shell_executable(),
            )
            logger.info(
                "[CMD] (background) user=%s cmd=%s workdir=%s pid=%s",
                user_id,
                cmd,
                workdir,
                proc.pid,
            )
            return RunResponse(
                ok=True,
                stdout="started (background)",
                stderr="",
                returncode=0,
                audit_id=f"{audit_id}-bg-pid-{proc.pid}",
            )

        success, stdout, stderr, rc = run_subprocess(
            cmd, cwd=workdir, timeout=timeout, merge_stderr=False
        )

        logger.info(
            "[CMD] user=%s cmd=%s workdir=%s rc=%s stdout_len=%s stderr_len=%s",
            user_id,
            cmd,
            workdir,
            rc,
            len(stdout),
            len(stderr),
        )

        return RunResponse(
            ok=success,
            stdout=stdout,
            stderr=stderr,
            returncode=rc,
            message=format_command_message(cmd, success, stdout, stderr),
            audit_id=audit_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[CMD] Failed to run command: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Command execution failed")
