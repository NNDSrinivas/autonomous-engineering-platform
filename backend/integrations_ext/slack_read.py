"""Slack Read Connector - read-only access to Slack channels and messages"""

import logging
import httpx
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SlackReader:
    def __init__(self, bot_token: str):
        self.token = bot_token

    async def list_channels(self, client: httpx.AsyncClient) -> List[Dict]:
        """List all public and private channels (no archived)"""
        r = await client.get(
            "https://slack.com/api/conversations.list",
            headers={"Authorization": f"Bearer {self.token}"},
            params={
                "exclude_archived": True,
                "types": "public_channel,private_channel",
            },
        )
        r.raise_for_status()
        j = r.json()
        if not j.get("ok"):
            logger.error("Slack API error in list_channels: %s", j.get("error", "unknown error"))
            return []
        return j.get("channels", [])

    async def history(
        self,
        client: httpx.AsyncClient,
        channel: str,
        oldest: Optional[str],
        limit=500,
    ) -> List[Dict]:
        """Get message history for a channel with optional cursor (oldest timestamp)"""
        params = {"channel": channel, "limit": limit}
        if oldest:
            params["oldest"] = oldest
        r = await client.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {self.token}"},
            params=params,
        )
        r.raise_for_status()
        j = r.json()
        if not j.get("ok"):
            logger.error(
                "Slack API error in history for channel %s: %s",
                channel,
                j.get("error", "unknown error"),
            )
            return []
        return j.get("messages", [])
