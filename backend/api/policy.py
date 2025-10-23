"""Policy management API endpoints"""

from fastapi import APIRouter, Depends, Body, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.db import get_db
import json
from typing import Dict, Any

router = APIRouter(prefix="/api/policy", tags=["policy"])


def require_role(db: Session, org_id: str, user_id: str, roles=("admin", "maintainer")):
    """Check if user has required role in organization"""
    row = (
        db.execute(
            text("SELECT role FROM org_user WHERE org_id=:o AND user_id=:u"),
            {"o": org_id, "u": user_id},
        )
        .mappings()
        .first()
    )

    if not row or row["role"] not in roles:
        raise HTTPException(403, "Forbidden: insufficient permissions")


@router.get("/", summary="Get organization policy")
def get_policy(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retrieve the current policy configuration for an organization.

    Headers:
        X-Org-Id: Organization identifier (defaults to 'default')

    Returns:
        Policy configuration object with all policy fields
    """
    org_id = request.headers.get("X-Org-Id") or "default"

    row = (
        db.execute(text("SELECT * FROM org_policy WHERE org_id=:o"), {"o": org_id})
        .mappings()
        .first()
    )

    if not row:
        return {}

    # Convert to dict and parse JSON fields
    policy = dict(row)
    json_fields = [
        "models_allow",
        "phase_budgets",
        "commands_allow",
        "commands_deny",
        "paths_allow",
        "repos_allow",
        "branches_protected",
        "require_review_for",
    ]

    for field in json_fields:
        if policy.get(field):
            try:
                policy[field] = json.loads(policy[field])
            except (json.JSONDecodeError, TypeError):
                pass

    return policy


@router.post("/", summary="Create or update organization policy")
def upsert_policy(
    payload: dict = Body(...), request: Request = None, db: Session = Depends(get_db)
) -> Dict[str, bool]:
    """
    Create or update policy configuration for an organization.
    Requires admin or maintainer role.

    Headers:
        X-Org-Id: Organization identifier
        X-User-Id: User identifier for permission check

    Request Body:
        Policy configuration object with fields:
        - models_allow: List[str] - Allowed model names
        - phase_budgets: Dict - Budget limits by phase
        - commands_allow: List[str] - Allowed command prefixes
        - commands_deny: List[str] - Denied command prefixes
        - paths_allow: List[str] - Allowed file path globs
        - repos_allow: List[str] - Allowed repositories
        - branches_protected: List[str] - Protected branch names
        - required_reviewers: int - Number of required approvals
        - require_review_for: List[str] - Action kinds requiring review

    Returns:
        Success indicator
    """
    org_id = request.headers.get("X-Org-Id") or "default"
    user_id = request.headers.get("X-User-Id") or "unknown"

    # Check permissions
    require_role(db, org_id, user_id, roles=("admin", "maintainer"))

    # Whitelist of allowed policy fields to prevent SQL injection
    ALLOWED_FIELDS = {
        "models_allow",
        "phase_budgets",
        "commands_allow",
        "commands_deny",
        "paths_allow",
        "repos_allow",
        "branches_protected",
        "required_reviewers",
        "require_review_for",
    }

    # Prepare fields for upsert - only allow whitelisted fields
    keys = [k for k in ALLOWED_FIELDS if k in payload]

    vals = {}
    for k in keys:
        value = payload.get(k)
        if value is not None:
            # Convert lists/dicts to JSON strings
            if isinstance(value, (list, dict)):
                vals[k] = json.dumps(value)
            else:
                vals[k] = value
        else:
            vals[k] = None

    # Check if policy exists
    exists = db.execute(
        text("SELECT 1 FROM org_policy WHERE org_id=:o"), {"o": org_id}
    ).fetchone()

    if exists:
        # Update existing policy - safe because keys are validated against ALLOWED_FIELDS whitelist
        update_sql = (
            "UPDATE org_policy SET "
            + ", ".join([f"{k}=:{k}" for k in keys])
            + " WHERE org_id=:o"
        )
        db.execute(text(update_sql), dict(vals, o=org_id))
    else:
        # Insert new policy - safe because keys are validated against ALLOWED_FIELDS whitelist
        insert_sql = (
            f"INSERT INTO org_policy (org_id, {', '.join(keys)}) "
            f"VALUES (:o, {', '.join(':' + k for k in keys)})"
        )
        db.execute(text(insert_sql), dict(vals, o=org_id))

    db.commit()
    return {"ok": True}


@router.get("/check", summary="Check if action is allowed by policy")
def check_policy_action(
    request: Request,
    kind: str = None,
    command: str = None,
    repo: str = None,
    branch: str = None,
    model: str = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Check if a specific action would be allowed by the current policy.
    Useful for pre-flight checks before executing actions.

    Query Parameters:
        kind: Action type (edit|cmd|git|pr|jira)
        command: Shell command (for cmd actions)
        repo: Repository name (for git/pr actions)
        branch: Branch name (for git actions)
        model: LLM model name (for LLM calls)

    Returns:
        Policy check result with allowed status and reasons
    """
    from ..policy.engine import check_action

    org_id = request.headers.get("X-Org-Id") or "default"

    policy = (
        db.execute(text("SELECT * FROM org_policy WHERE org_id=:o"), {"o": org_id})
        .mappings()
        .first()
    )

    if not policy:
        return {"allowed": True, "reasons": [], "require_review": False}

    action = {
        "kind": kind,
        "command": command,
        "repo": repo,
        "branch": branch,
        "model": model,
    }

    return check_action(dict(policy), action)
