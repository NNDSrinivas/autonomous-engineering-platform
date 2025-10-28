"""
Delivery schemas for PR creation and JIRA integration
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class DraftPRRequest(BaseModel):
    """Request schema for creating a draft PR"""

    repo_full_name: str = Field(
        ..., description="GitHub repository in format 'owner/repo'"
    )
    base: str = Field(..., description="Base branch (e.g., 'main')")
    head: str = Field(..., description="Head branch (e.g., 'feat/jwt-expiry')")
    title: str = Field(..., description="PR title")
    body: str = Field(..., description="PR body/description in markdown")
    ticket_key: Optional[str] = Field(
        None, description="Optional JIRA ticket key for auto-linking"
    )
    dry_run: bool = Field(
        True, description="If true, return preview without creating PR"
    )


class DraftPRResponse(BaseModel):
    """Response schema for draft PR creation"""

    existed: bool = Field(False, description="True if PR already exists")
    url: Optional[str] = Field(None, description="URL to the created or existing PR")
    number: Optional[int] = Field(None, description="PR number")
    preview: Optional[Dict[str, Any]] = Field(
        None, description="Preview payload for dry-run"
    )


class JiraCommentRequest(BaseModel):
    """Request schema for adding JIRA comments"""

    issue_key: str = Field(..., description="JIRA issue key (e.g., 'AEP-27')")
    comment: str = Field(..., description="Comment text to post")
    transition: Optional[str] = Field(
        None, description="Optional status transition name"
    )
    dry_run: bool = Field(
        True, description="If true, return preview without posting comment"
    )


class JiraCommentResponse(BaseModel):
    """Response schema for JIRA comment posting"""

    url: Optional[str] = Field(None, description="URL to the JIRA issue")
    preview: Optional[Dict[str, Any]] = Field(
        None, description="Preview payload for dry-run"
    )
    transition_result: Optional[Dict[str, Any]] = Field(
        None, description="Result of status transition if performed"
    )
    status: str = Field(
        ...,
        description="Operation status: 'success' or 'partial_success' (errors use HTTPException)",
    )
