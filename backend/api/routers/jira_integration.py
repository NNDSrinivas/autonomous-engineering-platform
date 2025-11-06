"""
Jira Integration API for VS Code Extension

Provides endpoints for accessing user's Jira tasks and integration data.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from backend.database.session import get_db
from sqlalchemy.orm import Session
from backend.api.routers.oauth_device import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/jira", tags=["Jira Integration"])


class JiraIssue(BaseModel):
    id: str = Field(description="Jira issue ID")
    key: str = Field(description="Jira issue key (e.g., PROJ-123)")
    summary: str = Field(description="Issue summary/title")
    status: str = Field(description="Issue status")
    priority: Optional[str] = Field(description="Issue priority")
    assignee: Optional[str] = Field(description="Assigned user")
    url: Optional[str] = Field(description="Link to Jira issue")
    project: Optional[str] = Field(description="Project key")
    issue_type: Optional[str] = Field(description="Issue type (Bug, Story, etc.)")
    created: Optional[str] = Field(description="Creation timestamp")
    updated: Optional[str] = Field(description="Last update timestamp")


@router.get("/my-issues", response_model=List[JiraIssue])
async def get_my_jira_issues(
    authorization: str = Header(None),
    limit: int = 10,
    status: Optional[str] = None,
    project: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get Jira issues assigned to the authenticated user.

    This endpoint provides the user's assigned Jira tasks for the morning briefing
    and task selection in the VS Code extension.
    """
    try:
        # Validate user authentication
        user = await get_current_user(authorization)
        user_id = user["user_id"]

        # For MVP, return mock data
        # In production, integrate with your Jira service
        mock_issues = [
            JiraIssue(
                id="10001",
                key="AEP-123",
                summary="Implement VS Code extension OAuth authentication",
                status="In Progress",
                priority="High",
                assignee=user_id,
                url="https://jira.company.com/browse/AEP-123",
                project="AEP",
                issue_type="Story",
                created="2024-11-05T10:00:00Z",
                updated="2024-11-05T15:30:00Z",
            ),
            JiraIssue(
                id="10002",
                key="AEP-124",
                summary="Add enterprise intelligence integration to morning briefings",
                status="To Do",
                priority="Medium",
                assignee=user_id,
                url="https://jira.company.com/browse/AEP-124",
                project="AEP",
                issue_type="Epic",
                created="2024-11-04T09:15:00Z",
                updated="2024-11-04T16:45:00Z",
            ),
            JiraIssue(
                id="10003",
                key="AEP-125",
                summary="Fix plan execution engine approval workflow",
                status="Review",
                priority="High",
                assignee=user_id,
                url="https://jira.company.com/browse/AEP-125",
                project="AEP",
                issue_type="Bug",
                created="2024-11-03T14:20:00Z",
                updated="2024-11-05T11:00:00Z",
            ),
        ]

        # Apply filters
        filtered_issues = mock_issues

        if status:
            filtered_issues = [
                issue
                for issue in filtered_issues
                if issue.status.lower() == status.lower()
            ]

        if project:
            filtered_issues = [
                issue for issue in filtered_issues if issue.project == project
            ]

        # Apply limit
        return filtered_issues[:limit]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user Jira issues: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch Jira issues: {str(e)}"
        )


@router.get("/issue/{issue_key}", response_model=JiraIssue)
async def get_jira_issue(
    issue_key: str, authorization: str = Header(None), db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific Jira issue.
    """
    try:
        user = await get_current_user(authorization)

        # For MVP, return mock data based on issue key
        if issue_key == "AEP-123":
            return JiraIssue(
                id="10001",
                key="AEP-123",
                summary="Implement VS Code extension OAuth authentication",
                status="In Progress",
                priority="High",
                assignee=user["user_id"],
                url="https://jira.company.com/browse/AEP-123",
                project="AEP",
                issue_type="Story",
                created="2024-11-05T10:00:00Z",
                updated="2024-11-05T15:30:00Z",
            )
        else:
            raise HTTPException(status_code=404, detail="Issue not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch Jira issue {issue_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch issue: {str(e)}")
