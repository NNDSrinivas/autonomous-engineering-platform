"""
Delivery API endpoints for GitHub PR creation and JIRA integration
"""

import logging
from fastapi import APIRouter, Depends, Body, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from ..core.database import get_db
from ..schemas.deliver import (
    DraftPRRequest, 
    DraftPRResponse, 
    JiraCommentRequest, 
    JiraCommentResponse
)
from ..services.github_write import GitHubWriteService
from ..services.jira_write import JiraWriteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deliver", tags=["delivery"])


def get_github_credentials(db: Session, org_id: str) -> str:
    """Get GitHub access token for the organization"""
    try:
        result = db.execute(
            text("""
                SELECT access_token, repo_full_name 
                FROM gh_connection 
                WHERE org_id = :org_id 
                ORDER BY created_at DESC 
                LIMIT 1
            """),
            {"org_id": org_id}
        ).mappings().first()
        
        if not result:
            raise HTTPException(
                status_code=400, 
                detail="No GitHub connection found for organization"
            )
        
        return result["access_token"]
        
    except Exception as e:
        logger.error(f"Failed to get GitHub credentials: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to retrieve GitHub credentials"
        )


def get_jira_credentials(db: Session, org_id: str) -> tuple[str, str, str]:
    """Get JIRA credentials for the organization"""
    try:
        result = db.execute(
            text("""
                SELECT base_url, access_token, email 
                FROM jira_connection 
                WHERE org_id = :org_id 
                ORDER BY created_at DESC 
                LIMIT 1
            """),
            {"org_id": org_id}
        ).mappings().first()
        
        if not result:
            raise HTTPException(
                status_code=400, 
                detail="No JIRA connection found for organization"
            )
        
        return result["base_url"], result["access_token"], result["email"]
        
    except Exception as e:
        logger.error(f"Failed to get JIRA credentials: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to retrieve JIRA credentials"
        )


def audit_delivery_action(
    db: Session, 
    service: str, 
    method: str, 
    path: str, 
    status: int,
    org_id: str,
    details: Dict[str, Any] = None
) -> None:
    """Record delivery action in audit log"""
    try:
        db.execute(
            text("""
                INSERT INTO audit_log (service, method, path, status, org_id, details, created_at) 
                VALUES (:service, :method, :path, :status, :org_id, :details, NOW())
            """),
            {
                "service": service,
                "method": method, 
                "path": path,
                "status": status,
                "org_id": org_id,
                "details": str(details) if details else None
            }
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
    db: Session = Depends(get_db)
) -> DraftPRResponse:
    """
    Create a draft PR on GitHub with RBAC and audit logging
    
    Supports dry-run mode for preview before execution.
    Automatically links JIRA tickets if provided.
    """
    # Get organization ID from headers (with fallback)
    org_id = http_request.headers.get("X-Org-Id", "default")
    
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
            dry_run=request.dry_run
        )
        
        # Audit the action
        audit_details = {
            "repo": request.repo_full_name,
            "base": request.base,
            "head": request.head,
            "dry_run": request.dry_run,
            "ticket_key": request.ticket_key
        }
        
        audit_delivery_action(
            db=db,
            service="delivery",
            method="POST",
            path="/github/draft-pr",
            status=200,
            org_id=org_id,
            details=audit_details
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
            details={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create draft PR: {str(e)}"
        )


@router.post("/jira/comment", response_model=JiraCommentResponse)
async def add_jira_comment(
    request: JiraCommentRequest = Body(...),
    http_request: Request = None,
    db: Session = Depends(get_db)
) -> JiraCommentResponse:
    """
    Add a comment to a JIRA issue with optional status transition
    
    Supports dry-run mode for preview before execution.
    Can optionally transition the issue status.
    """
    # Get organization ID from headers (with fallback)
    org_id = http_request.headers.get("X-Org-Id", "default")
    
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
            dry_run=request.dry_run
        )
        
        # Handle optional transition
        transition_result = None
        if request.transition and not request.dry_run:
            try:
                transition_result = await jira_service.transition_issue(
                    issue_key=request.issue_key,
                    transition_name=request.transition,
                    dry_run=request.dry_run
                )
            except Exception as e:
                logger.warning(f"Transition failed but comment succeeded: {e}")
                # Don't fail the whole operation if just transition fails
                transition_result = {"error": str(e)}
        elif request.transition and request.dry_run:
            # Include transition preview
            transition_result = await jira_service.transition_issue(
                issue_key=request.issue_key,
                transition_name=request.transition,
                dry_run=True
            )
        
        # Prepare response
        response_data = {
            "url": comment_result.get("url"),
            "preview": comment_result.get("preview"),
            "transition_result": transition_result
        }
        
        # If dry-run and transition requested, merge previews
        if request.dry_run and request.transition:
            if "preview" in comment_result and "preview" in transition_result:
                response_data["preview"]["transition"] = transition_result["preview"]
        
        # Audit the action
        audit_details = {
            "issue_key": request.issue_key,
            "has_transition": bool(request.transition),
            "dry_run": request.dry_run
        }
        
        audit_delivery_action(
            db=db,
            service="delivery",
            method="POST",
            path="/jira/comment",
            status=200,
            org_id=org_id,
            details=audit_details
        )
        
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
            details={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add JIRA comment: {str(e)}"
        )


@router.get("/health")
async def delivery_health_check():
    """Health check endpoint for delivery service"""
    return {"status": "healthy", "service": "delivery"}