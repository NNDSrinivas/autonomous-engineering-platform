# backend/schemas/connectors.py

from __future__ import annotations

from typing import List, Literal, Optional
from datetime import date
from pydantic import BaseModel, HttpUrl, Field


ConnectorId = Literal[
    "jira",
    "slack",
    "github",
    "teams",
    "meet",
    "zoom",
    "confluence",
    "gitlab",
    "jenkins",
]


class ConnectorStatus(BaseModel):
    """Per-connector status for the current user."""

    id: ConnectorId
    name: str
    category: str = "general"
    status: Literal["connected", "disconnected", "error"] = "disconnected"
    error: Optional[str] = None


class ConnectorStatusResponse(BaseModel):
    """Wrapper response for /api/connectors/status."""

    items: List[ConnectorStatus]
    offline: bool = False


class JiraConnectorRequest(BaseModel):
    """
    Minimal payload to connect Jira for a user (dev mode).

    - base_url: https://your-domain.atlassian.net
    - email + api_token: Jira basic auth (API token)
    - access_token + token_type: OAuth bearer token
    """

    base_url: HttpUrl = Field(..., description="Jira Cloud base URL")
    email: Optional[str] = Field(None, description="Jira user email")
    api_token: Optional[str] = Field(None, description="Jira API token or PAT")
    access_token: Optional[str] = Field(None, description="Jira OAuth access token")
    refresh_token: Optional[str] = Field(None, description="Jira OAuth refresh token")
    token_type: Optional[str] = Field(None, description="OAuth token type (Bearer)")


class SlackConnectorRequest(BaseModel):
    """
    Minimal payload to connect Slack for a user (dev mode).

    For now we just accept a bot token. Later this can become full OAuth.
    """

    bot_token: str = Field(..., description="Slack bot token (xoxb-…)")


class SlackSyncRequest(BaseModel):
    """Request to sync Slack messages into NAVI memory."""

    channels: List[str] = Field(
        default_factory=list, description="Slack channel names to sync"
    )
    limit: int = Field(200, ge=1, le=500, description="Max messages per channel")
    include_dms: bool = Field(False, description="Include direct messages")
    include_files: bool = Field(
        False,
        description="Attempt to download text attachments for summarization",
    )


class SlackSyncResponse(BaseModel):
    """Response from Slack sync operation."""

    processed_channel_ids: List[str]
    total: int


class GitHubRepoItem(BaseModel):
    """Minimal GitHub repo metadata for connector selection."""

    full_name: str
    private: bool = False
    html_url: Optional[str] = None
    default_branch: Optional[str] = None


class GitHubRepoListResponse(BaseModel):
    items: List[GitHubRepoItem]


class GitHubIndexRequest(BaseModel):
    repo_full_name: str = Field(..., description="owner/repo")


class GitHubIndexResponse(BaseModel):
    ok: bool
    repo_full_name: str
    webhook_registered: bool = False


class ConfluenceSyncRequest(BaseModel):
    """Request to sync Confluence pages by space key."""

    space_key: str = Field(..., description="Confluence space key, e.g. ENG")
    limit: int = Field(20, ge=1, le=200, description="Max pages per sync")


class ConfluenceSyncResponse(BaseModel):
    processed_page_ids: List[str]
    total: int


class ConfluenceSubscribeRequest(BaseModel):
    space_key: Optional[str] = Field(None, description="Optional space key to scope webhooks")


class ConfluenceSubscribeResponse(BaseModel):
    ok: bool
    webhook_id: Optional[str] = None


class TeamsTeamItem(BaseModel):
    id: str
    display_name: str


class TeamsTeamListResponse(BaseModel):
    items: List[TeamsTeamItem]


class TeamsChannelItem(BaseModel):
    id: str
    display_name: str


class TeamsChannelListResponse(BaseModel):
    items: List[TeamsChannelItem]


class TeamsSubscribeRequest(BaseModel):
    team_id: str
    channel_id: str


class TeamsSubscribeResponse(BaseModel):
    ok: bool
    subscription_id: str
    expires_at: Optional[str] = None


class ZoomSyncRequest(BaseModel):
    zoom_user: str = Field(..., description="Zoom user id or email")
    from_date: date
    to_date: date
    max_meetings: int = Field(20, ge=1, le=200)


class ZoomSyncResponse(BaseModel):
    processed_meeting_ids: List[str]
    total: int


class MeetSubscribeRequest(BaseModel):
    calendar_id: str = Field("primary", description="Google Calendar ID")


class MeetSubscribeResponse(BaseModel):
    ok: bool
    channel_id: str
    resource_id: Optional[str] = None
    expires_at: Optional[str] = None


class MeetSyncRequest(BaseModel):
    calendar_id: str = Field("primary", description="Google Calendar ID")
    days_back: int = Field(7, ge=1, le=90)
    include_transcripts: bool = Field(False, description="Attempt to ingest Meet transcripts")


class MeetSyncResponse(BaseModel):
    processed_event_ids: List[str]
    total: int


class ConnectorConnectResponse(BaseModel):
    ok: bool
    connector_id: ConnectorId
    error: Optional[str] = None


class OAuthAppConfigRequest(BaseModel):
    provider: ConnectorId
    client_id: str = Field(..., description="OAuth client ID for the provider")
    client_secret: Optional[str] = Field(
        None, description="OAuth client secret (omit to keep existing)"
    )
    scopes: Optional[str] = Field(None, description="OAuth scopes override")
    tenant_id: Optional[str] = Field(None, description="Tenant ID (Teams only)")
    account_id: Optional[str] = Field(None, description="Account ID (Zoom only)")
    extra: Optional[dict] = Field(None, description="Provider-specific metadata")


class OAuthAppConfigResponse(BaseModel):
    ok: bool
    provider: ConnectorId
    configured: bool = False
    client_id: Optional[str] = None
    scopes: Optional[str] = None
    tenant_id: Optional[str] = None
    account_id: Optional[str] = None
    extra: Optional[dict] = None


class OrgUiConfigRequest(BaseModel):
    base_url: Optional[str] = Field(None, description="Primary UI base URL for the org")
    allowed_domains: List[str] = Field(
        default_factory=list,
        description="Additional allowed UI origins for redirects",
    )
    redirect_path: Optional[str] = Field(
        None, description="Relative UI path for OAuth redirect"
    )


class OrgUiConfigResponse(BaseModel):
    ok: bool
    base_url: Optional[str] = None
    allowed_domains: List[str] = Field(default_factory=list)
    redirect_path: Optional[str] = None


class GenericConnectorRequest(BaseModel):
    provider: str
    name: Optional[str] = "default"
    base_url: Optional[str] = None
    token: Optional[str] = None
    workspace_root: Optional[str] = None
    extra: Optional[dict] = None


class GenericConnectorResponse(BaseModel):
    ok: bool
    connector_id: str
    id: Optional[int] = None
    error: Optional[str] = None


class ConnectorListItem(BaseModel):
    id: Optional[int]
    provider: str
    name: str
    config: dict
    workspace_root: Optional[str] = None


class ConnectorListResponse(BaseModel):
    items: list[ConnectorListItem]
