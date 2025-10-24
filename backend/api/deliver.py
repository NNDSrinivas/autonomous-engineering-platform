"""
Delivery API endpoints for GitHub PR creation and JIRA integration

This module provides endpoints for creating draft GitHub PRs and adding JIRA comments.
"""

import logging
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Body, HTTPException, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, Tuple

from ..core.db import get_db
from ..schemas.deliver import (
    DraftPRRequest,
    DraftPRResponse,
    JiraCommentRequest,
    JiraCommentResponse,
)
from ..services.github_write import GitHubWriteService
from ..services.jira_write import JiraWriteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deliver", tags=["delivery"])

# Cache for audit log table existence to avoid repeated checks
_audit_table_exists = None


def get_github_credentials(db: Session, org_id: str) -> str:
    """Get GitHub access token for the organization"""
    try:
        result = (
            db.execute(
                text(
                    """
                SELECT access_token 
                FROM gh_connection 
                WHERE org_id = :org_id 
                ORDER BY created_at DESC 
                LIMIT 1
            """
                ),
                {"org_id": org_id},
            )
            .mappings()
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=400, detail="No GitHub connection found for organization"
            )

        return result["access_token"]

    except Exception as e:
        logger.error(f"Failed to get GitHub credentials: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve GitHub credentials"
        )


def get_jira_credentials(db: Session, org_id: str) -> Tuple[str, str, str]:
    """Get JIRA credentials for the organization"""
    try:
        result = (
            db.execute(
                text(
                    """
                SELECT base_url, access_token, email 
                FROM jira_connection 
                WHERE org_id = :org_id 
                ORDER BY created_at DESC 
                LIMIT 1
            """
                ),
                {"org_id": org_id},
            )
            .mappings()
            .first()
        )

        if not result:
            raise HTTPException(
                status_code=400, detail="No JIRA connection found for organization"
            )

        return result["base_url"], result["access_token"], result["email"]

    except Exception as e:
        logger.error(f"Failed to get JIRA credentials: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve JIRA credentials"
        )


def audit_delivery_action(
    db: Session,
    service: str,
    method: str,
    path: str,
    status: int,
    org_id: str,
    details: Dict[str, Any] = None,
) -> None:
    """Record delivery action in audit log"""
    global _audit_table_exists

    try:
        # Check table existence once and cache the result
        if _audit_table_exists is None:
            table_check = db.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
                )
            ).fetchone()
            _audit_table_exists = table_check is not None

        if not _audit_table_exists:
            logger.warning("Audit log table does not exist, skipping audit logging")
            return

        db.execute(
            text(
                """
                INSERT INTO audit_log (service, method, path, status, org_id, details, created_at) 
                VALUES (:service, :method, :path, :status, :org_id, :details, :created_at)
            """
            ),
            {
                "service": service,
                "method": method,
                "path": path,
                "status": status,
                "org_id": org_id,
                "details": json.dumps(details) if details else None,
                "created_at": datetime.now(timezone.utc),
            },
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to audit delivery action: {e}")
        # Don't fail the main operation for audit failures
        db.rollback()


@router.post("/github/draft-pr", response_model=DraftPRResponse)
async def create_draft_pr(
    request: DraftPRRequest = Body(...),
    http_request: Request = None,
    db: Session = Depends(get_db),
) -> DraftPRResponse:
    """
    Create a draft PR on GitHub with optional JIRA ticket linking.

    Requires the 'X-Org-Id' header to specify the organization context.
    Supports dry-run mode for preview before execution.
    Automatically links JIRA tickets if provided.
    """
    # Require organization ID from headers
    org_id = http_request.headers.get("X-Org-Id")
    if not org_id:
        raise HTTPException(
            status_code=400, detail="Missing required 'X-Org-Id' header"
        )

    try:
        logger.info(f"Creating draft PR for org {org_id}: {request.repo_full_name}")

        # Get GitHub credentials for the organization
        github_token = get_github_credentials(db, org_id)

        # Initialize GitHub service
        github_service = GitHubWriteService(github_token)

        # Create or check for existing PR
        result = await github_service.draft_pr(
            repo_full_name=request.repo_full_name,
            base=request.base,
            head=request.head,
            title=request.title,
            body=request.body,
            ticket_key=request.ticket_key,
            dry_run=request.dry_run,
        )

        # Audit the action
        audit_details = {
            "repo": request.repo_full_name,
            "base": request.base,
            "head": request.head,
            "dry_run": request.dry_run,
            "ticket_key": request.ticket_key,
        }

        audit_delivery_action(
            db=db,
            service="delivery",
            method="POST",
            path="/github/draft-pr",
            status=200,
            org_id=org_id,
            details=audit_details,
        )

        logger.info(f"Draft PR operation completed: {result}")
        return DraftPRResponse(**result)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to create draft PR: {e}")

        # Audit the failure
        audit_delivery_action(
            db=db,
            service="delivery",
            method="POST",
            path="/github/draft-pr",
            status=500,
            org_id=org_id,
            details={"error": str(e)},
        )

        raise HTTPException(
            status_code=500, detail=f"Failed to create draft PR: {str(e)}"
        )


@router.post("/jira/comment", response_model=JiraCommentResponse)
async def add_jira_comment(
    request: JiraCommentRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> JiraCommentResponse:
    """
    Add a comment to a JIRA issue with optional status transition.

    Requires the 'X-Org-Id' header to specify the organization context.
    Supports dry-run mode for preview before execution.
    Can optionally transition the issue status.

    Returns appropriate HTTP status codes following REST conventions:
    - 200 OK: Complete success (comment and transition both succeeded)
    - 200 OK: Partial success (comment succeeded but transition failed; indicated by status field)
    - 500 Internal Server Error: Complete failure

    The response includes a 'status' field for programmatic handling in success responses:
    - status: 'success' - Both comment and transition completed successfully (HTTP 200)
    - status: 'partial_success' - Comment succeeded but transition failed (HTTP 200)

    Note: Complete failures return HTTP 500 with HTTPException, not a response with status field.

    This design prioritizes comment delivery over transition consistency while
    following proper REST semantics (HTTP 200 for both complete and partial success, with status field indicating outcome).
    """
    # Require organization ID from headers
    org_id = http_request.headers.get("X-Org-Id")
    if not org_id:
        raise HTTPException(
            status_code=400, detail="Missing required 'X-Org-Id' header"
        )

    try:
        logger.info(f"Adding JIRA comment for org {org_id}: {request.issue_key}")

        # Get JIRA credentials for the organization
        jira_base_url, jira_token, jira_email = get_jira_credentials(db, org_id)

        # Initialize JIRA service
        jira_service = JiraWriteService(jira_base_url, jira_token, jira_email)

        # Add comment
        comment_result = await jira_service.add_comment(
            issue_key=request.issue_key,
            comment=request.comment,
            dry_run=request.dry_run,
        )

        # Handle optional transition
        transition_result = None
        if request.transition and not request.dry_run:
            try:
                transition_result = await jira_service.transition_issue(
                    issue_key=request.issue_key,
                    transition_name=request.transition,
                    dry_run=request.dry_run,
                )
            except Exception as e:
                logger.warning(f"Transition failed but comment succeeded: {e}")
                # Don't fail the whole operation if just transition fails
                transition_result = {
                    "error": str(e),
                    "transition_name": request.transition,
                    "issue_key": request.issue_key,
                }
        elif request.transition and request.dry_run:
            # Include transition preview
            transition_result = await jira_service.transition_issue(
                issue_key=request.issue_key,
                transition_name=request.transition,
                dry_run=True,
            )

        # Determine operation status and HTTP status code
        operation_status = "success"
        http_status = 200
        if request.transition and not request.dry_run:
            # Check if transition failed while comment succeeded
            if transition_result and "error" in transition_result:
                operation_status = "partial_success"
                http_status = 200  # Use 200 OK for partial success, as documented

        # Prepare response
        response_data = {
            "url": comment_result.get("url"),
            "preview": comment_result.get("preview"),
            "transition_result": transition_result,
            "status": operation_status,
        }

        # If dry-run and transition requested, merge previews
        if request.dry_run and request.transition:
            if "preview" in comment_result and "preview" in transition_result:
                response_data["preview"]["transition"] = transition_result["preview"]

        # Audit the action
        audit_details = {
            "issue_key": request.issue_key,
            "has_transition": bool(request.transition),
            "dry_run": request.dry_run,
        }

        audit_delivery_action(
            db=db,
            service="delivery",
            method="POST",
            path="/jira/comment",
            status=http_status,
            org_id=org_id,
            details=audit_details,
        )

        # Set HTTP status code
        response.status_code = http_status

        logger.info(f"JIRA comment operation completed: {request.issue_key}")
        return JiraCommentResponse(**response_data)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to add JIRA comment: {e}")

        # Audit the failure
        audit_delivery_action(
            db=db,
            service="delivery",
            method="POST",
            path="/jira/comment",
            status=500,
            org_id=org_id,
            details={"error": str(e)},
        )

        raise HTTPException(
            status_code=500, detail=f"Failed to add JIRA comment: {str(e)}"
        )


@router.get("/health")
async def delivery_health_check():
    """Health check endpoint for delivery service"""
    return {"status": "healthy", "service": "delivery"}
