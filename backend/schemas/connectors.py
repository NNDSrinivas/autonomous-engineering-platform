# backend/schemas/connectors.py

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, HttpUrl, Field


ConnectorId = Literal[
    "jira",
    "slack",
    "github",
    "teams",
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
    - email: Jira user email
    - api_token: personal API token
    """

    base_url: HttpUrl = Field(..., description="Jira Cloud base URL")
    email: str = Field(..., description="Jira user email")
    api_token: str = Field(..., description="Jira API token or PAT")


class SlackConnectorRequest(BaseModel):
    """
    Minimal payload to connect Slack for a user (dev mode).

    For now we just accept a bot token. Later this can become full OAuth.
    """

    bot_token: str = Field(..., description="Slack bot token (xoxb-…)")


class ConnectorConnectResponse(BaseModel):
    ok: bool
    connector_id: ConnectorId
    error: Optional[str] = None