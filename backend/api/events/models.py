from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class IngestEvent(BaseModel):
    """
    Universal event schema for all connector types.
    This normalizes events from Jira, Slack, GitHub, Zoom, Teams, Jenkins, etc.
    into a consistent format for NAVI memory ingestion.
    """

    source: str = Field(
        ...,
        description="Source system: jira, slack, github, zoom, teams, jenkins, confluence, etc.",
    )
    event_type: str = Field(
        ...,
        description="Type of event: issue_updated, comment_added, message_sent, pr_merged, etc.",
    )
    external_id: str = Field(
        ...,
        description="External identifier: SCRUM-1, commit sha, slack timestamp, etc.",
    )
    url: Optional[str] = Field(None, description="Canonical link to the item")
    title: Optional[str] = Field(None, description="Title or subject of the item")
    summary: Optional[str] = Field(None, description="Brief summary or description")
    content: Optional[str] = Field(
        None, description="Full body content, transcript, or message text"
    )
    user_id: str = Field(..., description="User ID who owns this context")
    org_id: Optional[str] = Field(None, description="Organization identifier")
    occurred_at: Optional[datetime] = Field(None, description="When the event occurred")
    tags: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata and tags"
    )
    importance: Optional[int] = Field(
        default=3, ge=1, le=5, description="Importance level 1-5"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class IngestResponse(BaseModel):
    """Response from event ingestion"""

    status: str
    memory_id: Optional[str] = None
    message: Optional[str] = None


class IngestBatchRequest(BaseModel):
    """Batch ingestion for multiple events"""

    events: list[IngestEvent]


class IngestBatchResponse(BaseModel):
    """Response from batch ingestion"""

    status: str
    processed: int
    failed: int
    memory_ids: list[str]
    errors: list[str] = []
