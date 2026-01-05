"""Microsoft Teams client for NAVI memory integration

This client fetches messages from Teams channels via Microsoft Graph API
and prepares them for ingestion into NAVI's memory system.
"""

import os
from typing import List, Dict, Any, Optional

import msal
import requests
import structlog

logger = structlog.get_logger(__name__)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class TeamsClient:
    """
    Microsoft Teams client via Microsoft Graph API.

    Supports:
    - Listing teams
    - Listing channels in a team
    - Fetching channel messages

    Requires Azure AD app with permissions:
    - ChannelMessage.Read.All
    - Group.Read.All
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id or os.getenv("AEP_MS_TENANT_ID", "")
        self.client_id = client_id or os.getenv("AEP_MS_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("AEP_MS_CLIENT_SECRET", "")
        self._token = access_token

        if not self._token and (
            not self.tenant_id or not self.client_id or not self.client_secret
        ):
            raise RuntimeError(
                "TeamsClient requires either an access token or "
                "AEP_MS_TENANT_ID, AEP_MS_CLIENT_ID, AEP_MS_CLIENT_SECRET."
            )
        logger.info("TeamsClient initialized", tenant_id=self.tenant_id)

    def _acquire_token(self) -> str:
        """Acquire OAuth token using client credentials flow."""
        if self._token:
            return self._token

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if result is None or "access_token" not in result:
            error_desc = (
                result.get("error_description", "Unknown error")
                if result
                else "No result returned"
            )
            logger.error("MSAL token acquisition failed", error=error_desc)
            raise RuntimeError(f"MSAL token error: {error_desc}")

        # Type assertion: result is Dict[str, Any], access_token is present after check
        access_token = result["access_token"]
        if not isinstance(access_token, str):
            raise RuntimeError(f"Unexpected access_token type: {type(access_token)}")
        self._token = access_token
        logger.debug("Acquired Microsoft Graph access token")
        return self._token

    def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated GET request to Microsoft Graph."""
        token = self._acquire_token()
        url = f"{GRAPH_BASE}{path}"

        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )

        if not resp.ok:
            logger.error(
                "Graph API request failed",
                url=url,
                status_code=resp.status_code,
                error=resp.text[:300],
            )
            raise RuntimeError(
                f"Graph GET {url} failed: {resp.status_code} {resp.text[:300]}"
            )

        return resp.json()

    def list_teams(self) -> List[Dict[str, Any]]:
        """
        List all teams the app has access to.

        Returns:
            List of team dictionaries with id, displayName, etc.
        """
        data = self._get("/me/joinedTeams")
        teams = data.get("value", [])
        logger.info("Listed Teams teams", count=len(teams))
        return teams

    def list_channels(self, team_id: str) -> List[Dict[str, Any]]:
        """
        List channels in a team.

        Args:
            team_id: Microsoft Teams team ID

        Returns:
            List of channel dictionaries
        """
        data = self._get(f"/teams/{team_id}/channels")
        channels = data.get("value", [])
        logger.debug("Listed team channels", team_id=team_id, count=len(channels))
        return channels

    def get_team_by_display_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find team by displayName.

        Args:
            name: Team display name

        Returns:
            Team dictionary or None if not found
        """
        teams = self.list_teams()
        name_lower = name.lower()
        for t in teams:
            if (t.get("displayName") or "").lower() == name_lower:
                logger.debug("Found team by name", name=name, team_id=t.get("id"))
                return t
        logger.warning("Team not found", name=name)
        return None

    def get_channel_by_display_name(
        self, team_id: str, name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find channel by displayName within a team.

        Args:
            team_id: Team ID
            name: Channel display name

        Returns:
            Channel dictionary or None if not found
        """
        chans = self.list_channels(team_id)
        name_lower = name.lower()
        for c in chans:
            if (c.get("displayName") or "").lower() == name_lower:
                logger.debug("Found channel by name", name=name, channel_id=c.get("id"))
                return c
        logger.warning("Channel not found", team_id=team_id, name=name)
        return None

    def fetch_channel_messages(
        self,
        team_id: str,
        channel_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages from a Teams channel.

        Args:
            team_id: Team ID
            channel_id: Channel ID
            limit: Maximum number of messages to fetch

        Returns:
            List of message dictionaries
        """
        messages: List[Dict[str, Any]] = []
        path = f"/teams/{team_id}/channels/{channel_id}/messages"

        try:
            data = self._get(path, params={"$top": min(limit, 50)})
            messages.extend(data.get("value", []))

            logger.info(
                "Fetched Teams channel messages",
                team_id=team_id,
                channel_id=channel_id,
                count=len(messages),
            )

            # NOTE: For simplicity, we don't follow @odata.nextLink here.
            # Can be extended for deeper history if needed.

        except Exception as e:
            logger.error(
                "Failed to fetch channel messages",
                team_id=team_id,
                channel_id=channel_id,
                error=str(e),
            )
            raise

        return messages

    def get_channel_message(
        self,
        team_id: str,
        channel_id: str,
        message_id: str,
    ) -> Dict[str, Any]:
        """
        Fetch a single message by ID from a Teams channel.
        """
        return self._get(
            f"/teams/{team_id}/channels/{channel_id}/messages/{message_id}"
        )
