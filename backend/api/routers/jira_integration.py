"""
Jira Integration API for VS Code Extension

Provides endpoints for accessing user's Jira tasks and integration data.
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.api.routers.oauth_device import get_current_user
from backend.core.db import get_db
from sqlalchemy.orm import Session
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


def _build_assignee_jql(status: Optional[str], project: Optional[str]) -> str:
    clauses = ["assignee = currentUser()"]
    if status:
        clauses.append(f'status = "{status}"')
    else:
        clauses.append("statusCategory != Done")
    if project:
        clauses.append(f'project = "{project}"')
    return " AND ".join(clauses) + " ORDER BY updated DESC"


def _issue_to_model(issue: Dict[str, Any], base_url: str) -> JiraIssue:
    fields = issue.get("fields", {}) or {}
    key = issue.get("key", "") or ""
    return JiraIssue(
        id=str(issue.get("id") or ""),
        key=key,
        summary=fields.get("summary") or "",
        status=(fields.get("status") or {}).get("name", "Unknown"),
        priority=(fields.get("priority") or {}).get("name"),
        assignee=(fields.get("assignee") or {}).get("displayName"),
        url=f"{base_url}/browse/{key}" if base_url and key else None,
        project=(fields.get("project") or {}).get("key"),
        issue_type=(fields.get("issuetype") or {}).get("name"),
        created=fields.get("created"),
        updated=fields.get("updated"),
    )


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

        from backend.services.org_ingestor import _get_jira_client_for_user

        jira_client = await _get_jira_client_for_user(db, user_id)
        if not jira_client:
            raise HTTPException(
                status_code=404,
                detail="No Jira connection configured for this user.",
            )

        jql = _build_assignee_jql(status=status, project=project)
        async with jira_client as jira:
            issues = await jira.get_assigned_issues(jql=jql, max_results=limit)

        return [_issue_to_model(issue, jira_client.base_url) for issue in issues]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user Jira issues: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch Jira issues: {str(e)}"
        )


@router.get("/issue/{issue_key}", response_model=JiraIssue)
async def get_jira_issue(
    issue_key: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific Jira issue.
    """
    try:
        user = await get_current_user(authorization)
        user_id = user["user_id"]
        issue_key = issue_key.strip().upper()

        from backend.services.org_ingestor import _get_jira_client_for_user

        jira_client = await _get_jira_client_for_user(db, user_id)
        if not jira_client:
            raise HTTPException(
                status_code=404,
                detail="No Jira connection configured for this user.",
            )

        async with jira_client as jira:
            issue = await jira.get_issue(issue_key)

        return _issue_to_model(issue, jira_client.base_url)

    except HTTPException:
        raise
    except RuntimeError as e:
        if " 404 " in str(e) or "404" in str(e):
            raise HTTPException(status_code=404, detail="Issue not found") from e
        logger.error(f"Jira API error for {issue_key}: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to fetch Jira issue from Jira API"
        ) from e
    except Exception as e:
        logger.error(f"Failed to fetch Jira issue {issue_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch issue: {str(e)}")
