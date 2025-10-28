"""Change request and approval workflow API endpoints"""

from fastapi import APIRouter, Depends, Body, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.db import get_db
from ..policy.engine import check_action, _as_list
import json
from typing import Dict, Any, List

router = APIRouter(prefix="/api/change", tags=["change"])


@router.post("/request", summary="Submit change request for approval")
def submit_change(
    payload: dict = Body(...), request: Request = None, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Submit a change request containing proposed actions/steps.
    The request will be validated against org policy and either
    auto-approved or put into pending state for review.

    Headers:
        X-Org-Id: Organization identifier
        X-User-Id: User identifier

    Request Body:
        - title: str - Change request title
        - ticket_key: str - Associated ticket/issue key
        - plan: Dict - Plan object with 'items' array of steps
        - patch_summary: str (optional) - Preview of changes
        - actions_meta: List[Dict] (optional) - Additional action metadata

    Returns:
        - accepted: bool - Whether request was accepted
        - change_id: int - ID of created change request (if accepted)
        - status: str - 'pending' or 'approved'
        - violations: List - Policy violations (if not accepted)
    """
    org = request.headers.get("X-Org-Id") or "default"
    user = request.headers.get("X-User-Id") or "unknown"

    # Load organization policy
    policy = (
        db.execute(text("SELECT * FROM org_policy WHERE org_id=:o"), {"o": org}).mappings().first()
        or {}
    )

    items = payload.get("plan", {}).get("items", [])

    # Validate each step against policy
    violations = []
    for it in items:
        verdict = check_action(
            dict(policy),
            {
                "kind": it.get("kind"),
                "command": it.get("command"),
                "files": it.get("files"),
                "repo": it.get("repo"),
                "branch": it.get("branch"),
                "model": it.get("model"),
                "phase": it.get("phase"),
            },
        )

        if not verdict["allowed"]:
            violations.append(
                {
                    "id": it.get("id"),
                    "kind": it.get("kind"),
                    "reasons": verdict["reasons"],
                }
            )

    # Reject if there are policy violations
    if violations:
        return {"accepted": False, "violations": violations}

    # Check if any step requires review
    require_list = _as_list(policy.get("require_review_for"))
    needs_review = any(it.get("kind") in set(require_list) for it in items)
    status = "pending" if needs_review else "approved"

    # Create change request
    res = db.execute(
        text(
            """
        INSERT INTO change_request (org_id, user_id, ticket_key, title, plan_json, patch_summary, status)
        VALUES (:o, :u, :t, :title, :plan, :patch, :status)
        RETURNING id
    """
        ),
        {
            "o": org,
            "u": user,
            "t": payload.get("ticket_key"),
            "title": payload.get("title"),
            "plan": json.dumps(payload.get("plan")),
            "patch": payload.get("patch_summary"),
            "status": status,
        },
    ).first()

    db.commit()

    return {
        "accepted": True,
        "change_id": res[0],
        "status": status,
        "needs_review": needs_review,
    }


@router.get("/{change_id}", summary="Get change request details")
def get_change(change_id: int, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Retrieve details of a specific change request.

    Returns:
        Change request details including plan, status, and reviews
    """
    org = request.headers.get("X-Org-Id") or "default"

    cr = (
        db.execute(
            text(
                """
        SELECT id, org_id, user_id, ticket_key, title, plan_json, patch_summary, status, created_at
        FROM change_request
        WHERE id=:id AND org_id=:o
    """
            ),
            {"id": change_id, "o": org},
        )
        .mappings()
        .first()
    )

    if not cr:
        raise HTTPException(404, "Change request not found")

    # Get reviews
    reviews = (
        db.execute(
            text(
                """
        SELECT reviewer_id, decision, comment, created_at
        FROM change_review
        WHERE change_id=:id
        ORDER BY created_at
    """
            ),
            {"id": change_id},
        )
        .mappings()
        .all()
    )

    result = dict(cr)
    result["reviews"] = [dict(r) for r in reviews]

    # Parse plan_json
    if result.get("plan_json"):
        try:
            result["plan"] = json.loads(result["plan_json"])
        except json.JSONDecodeError:
            result["plan"] = {}

    return result


@router.post("/{change_id}/review", summary="Approve or reject change request")
def review_change(
    change_id: int,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Submit a review (approve/reject) for a change request.
    Requires maintainer or admin role.

    Request Body:
        - decision: str - 'approve' or 'reject'
        - comment: str (optional) - Review comment

    Returns:
        - ok: bool - Success indicator
        - approvals: int - Current number of approvals
        - required: int - Required number of approvals
        - status: str - Current CR status
    """
    org = request.headers.get("X-Org-Id") or "default"
    user = request.headers.get("X-User-Id") or "unknown"

    # Check reviewer has required role
    role = (
        db.execute(
            text("SELECT role FROM org_user WHERE org_id=:o AND user_id=:u"),
            {"o": org, "u": user},
        )
        .mappings()
        .first()
    )

    if not role or role["role"] not in ("admin", "maintainer"):
        raise HTTPException(403, "Forbidden: only maintainers/admins can review changes")

    decision = payload.get("decision")
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "Invalid decision: must be 'approve' or 'reject'")

    # Check if change request exists and is pending
    cr = (
        db.execute(
            text(
                """
        SELECT status FROM change_request WHERE id=:id AND org_id=:o
    """
            ),
            {"id": change_id, "o": org},
        )
        .mappings()
        .first()
    )

    if not cr:
        raise HTTPException(404, "Change request not found")

    if cr["status"] != "pending":
        raise HTTPException(400, f"Change request is already {cr['status']}")

    # Record review
    db.execute(
        text(
            """
        INSERT INTO change_review (change_id, reviewer_id, decision, comment)
        VALUES (:c, :u, :d, :m)
    """
        ),
        {"c": change_id, "u": user, "d": decision, "m": payload.get("comment")},
    )

    # Check if we have enough approvals (query after INSERT to include current review)
    req = (
        db.execute(
            text("SELECT required_reviewers FROM org_policy WHERE org_id=:o"),
            {"o": org},
        )
        .mappings()
        .first()
    )

    # Default to 1 if required_reviewers is NULL or missing, ensure it's an int
    need = int((req.get("required_reviewers") or 1) if req else 1)

    ok_count = db.execute(
        text(
            """
        SELECT count(*) c FROM change_review WHERE change_id=:c AND decision='approve'
    """
        ),
        {"c": change_id},
    ).scalar()

    new_status = cr["status"]

    # Update CR status based on reviews (both ok_count and need are now guaranteed ints)
    if ok_count >= need:
        db.execute(
            text("UPDATE change_request SET status='approved' WHERE id=:c"),
            {"c": change_id},
        )
        new_status = "approved"
    elif decision == "reject":
        db.execute(
            text("UPDATE change_request SET status='rejected' WHERE id=:c"),
            {"c": change_id},
        )
        new_status = "rejected"

    db.commit()

    return {
        "ok": True,
        "approvals": int(ok_count),
        "required": int(need),
        "status": new_status,
    }


@router.get("/", summary="List change requests")
def list_changes(
    request: Request,
    status: str = None,
    user_id: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    List change requests for the organization with optional filters.

    Query Parameters:
        status: Filter by status (pending|approved|rejected)
        user_id: Filter by user who created the request
        limit: Maximum number of results (default 50)

    Returns:
        List of change request summaries
    """
    org = request.headers.get("X-Org-Id") or "default"

    sql = "SELECT id, user_id, ticket_key, title, status, created_at FROM change_request WHERE org_id=:o"
    params = {"o": org}

    if status:
        sql += " AND status=:status"
        params["status"] = status

    if user_id:
        sql += " AND user_id=:user"
        params["user"] = user_id

    sql += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit

    results = db.execute(text(sql), params).mappings().all()

    return [dict(r) for r in results]
