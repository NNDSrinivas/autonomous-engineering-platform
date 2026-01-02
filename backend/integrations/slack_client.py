"""Slack client for NAVI memory integration

This client fetches messages, threads, and channel history from Slack
and prepares them for ingestion into NAVI's memory system.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional

import httpx

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import structlog

logger = structlog.get_logger(__name__)


class SlackClient:
    """
    Slack Web API client for AEP NAVI memory integration.

    Supports:
    - Channel history
    - Thread replies
    - User lookup
    """

    def __init__(self, bot_token: Optional[str] = None):
        self.token = bot_token or os.getenv("AEP_SLACK_BOT_TOKEN", "")
        if not self.token:
            raise RuntimeError(
                "SlackClient is not configured. Set AEP_SLACK_BOT_TOKEN."
            )
        self.client = WebClient(token=self.token)
        logger.info("SlackClient initialized")

    def list_channels(self) -> List[Dict[str, Any]]:
        """
        List all public and private channels the bot has access to.

        Returns:
            List of channel dictionaries with id, name, and metadata
        """
        return self.list_conversations(types="public_channel,private_channel")

    def list_direct_messages(self) -> List[Dict[str, Any]]:
        """
        List IM/MPIM conversations the token can access.
        """
        return self.list_conversations(types="im,mpim")

    def list_conversations(self, types: str) -> List[Dict[str, Any]]:
        """
        List conversations by Slack API type string.

        Args:
            types: Comma-separated Slack conversation types.
        """
        channels: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        try:
            while True:
                res = self.client.conversations_list(
                    exclude_archived=True,
                    types=types,
                    limit=200,
                    cursor=cursor,
                )
                channels.extend(res.get("channels", []))
                cursor = (res.get("response_metadata") or {}).get("next_cursor")
                if not cursor:
                    break
            logger.info("Listed Slack conversations", count=len(channels), types=types)
            return channels
        except SlackApiError as e:
            logger.error("Failed to list Slack conversations", error=e.response["error"])
            raise RuntimeError(f"Slack API error: {e.response['error']}")

    def fetch_channel_messages(
        self,
        channel_id: str,
        limit: int = 200,
        oldest: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages from a Slack channel.

        Args:
            channel_id: Slack channel ID (e.g., C0382ACD1)
            limit: Maximum number of messages to fetch
            oldest: Unix timestamp to fetch messages after

        Returns:
            List of message dictionaries
        """
        try:
            res = self.client.conversations_history(
                channel=channel_id, limit=limit, oldest=oldest, inclusive=False
            )
            messages = res.get("messages", [])
            logger.info(
                "Fetched channel messages", channel_id=channel_id, count=len(messages)
            )
            return messages
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            if error_code == "not_in_channel":
                logger.info(
                    "Bot not in channel, attempting to join", channel_id=channel_id
                )
                if self.join_channel(channel_id):
                    # Retry after joining
                    try:
                        res = self.client.conversations_history(
                            channel=channel_id,
                            limit=limit,
                            oldest=oldest,
                            inclusive=False,
                        )
                        messages = res.get("messages", [])
                        logger.info(
                            "Fetched channel messages after joining",
                            channel_id=channel_id,
                            count=len(messages),
                        )
                        return messages
                    except SlackApiError:
                        logger.warning(
                            "Still cannot access channel after joining",
                            channel_id=channel_id,
                        )
                        return []
                else:
                    logger.warning("Cannot join channel", channel_id=channel_id)
                    return []
            else:
                logger.error(
                    "Failed to fetch channel messages",
                    channel_id=channel_id,
                    error=error_code,
                )
                raise RuntimeError(f"Slack API error: {error_code}")

    def join_channel(self, channel_id: str) -> bool:
        """
        Join a channel (for public channels) or get invited to private channels.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if successfully joined, False otherwise
        """
        try:
            self.client.conversations_join(channel=channel_id)
            logger.info("Successfully joined channel", channel_id=channel_id)
            return True
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            if error_code == "is_archived":
                logger.warning("Cannot join archived channel", channel_id=channel_id)
            elif error_code == "channel_not_found":
                logger.warning("Channel not found", channel_id=channel_id)
            elif error_code == "is_private":
                logger.info(
                    "Cannot auto-join private channel - invite required",
                    channel_id=channel_id,
                )
            else:
                logger.warning(
                    "Failed to join channel", channel_id=channel_id, error=error_code
                )
            return False

    def fetch_thread_replies(
        self, channel_id: str, thread_ts: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch all replies in a thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (parent message)

        Returns:
            List of messages in the thread (including parent)
        """
        try:
            res = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=200,
            )
            messages = res.get("messages", [])
            logger.debug(
                "Fetched thread replies",
                channel_id=channel_id,
                thread_ts=thread_ts,
                count=len(messages),
            )
            return messages
        except SlackApiError as e:
            logger.error(
                "Failed to fetch thread replies",
                channel_id=channel_id,
                thread_ts=thread_ts,
                error=e.response["error"],
            )
            raise RuntimeError(f"Slack thread error: {e.response['error']}")

    def get_user_name(self, user_id: str) -> str:
        """
        Get user's real name from user ID.

        Args:
            user_id: Slack user ID (e.g., U0382ACD1)

        Returns:
            User's real name or user_id if lookup fails
        """
        try:
            res = self.client.users_info(user=user_id)
            name = res.get("user", {}).get("real_name", user_id)
            return name
        except SlackApiError:
            logger.warning("Failed to get user name", user_id=user_id)
            return user_id

    def get_channel_name(self, channel_id: str) -> str:
        """
        Get channel name from channel ID.

        Args:
            channel_id: Slack channel ID

        Returns:
            Channel name or channel_id if lookup fails
        """
        try:
            res = self.client.conversations_info(channel=channel_id)
            name = res.get("channel", {}).get("name", channel_id)
            return name
        except SlackApiError:
            logger.warning("Failed to get channel name", channel_id=channel_id)
            return channel_id

    def auth_test(self) -> Dict[str, Any]:
        """
        Validate the current token against Slack.

        Returns the auth.test payload (team_id, user_id, bot_id, etc.).
        """
        try:
            response = self.client.auth_test()
            return getattr(response, "data", response)
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            logger.error("Slack auth.test failed", error=error_code)
            raise RuntimeError(f"Slack API error: {error_code}")

    async def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Post a message to Slack.

        This is async-friendly by running the blocking Slack SDK call in a thread.
        """
        payload: Dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        if attachments:
            payload["attachments"] = attachments

        try:
            response = await asyncio.to_thread(self.client.chat_postMessage, **payload)
            return getattr(response, "data", response)
        except SlackApiError as e:
            error_code = e.response.get("error", "unknown")
            logger.error("Failed to post Slack message", error=error_code)
            raise RuntimeError(f"Slack API error: {error_code}")

    async def fetch_file_content(
        self,
        file_info: Dict[str, Any],
        *,
        max_bytes: int = 200_000,
    ) -> Optional[str]:
        """
        Download a Slack file (if available) and return text content.

        Returns None if file is missing, too large, or download fails.
        """
        url = file_info.get("url_private_download") or file_info.get("url_private")
        if not url:
            return None
        size = file_info.get("size")
        if size and size > max_bytes:
            logger.info("Skipping Slack file (too large)", size=size)
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.token}"},
                )
            if resp.status_code >= 400:
                logger.warning(
                    "Slack file download failed", status=resp.status_code, url=url
                )
                return None
            content = resp.content[:max_bytes]
            return content.decode("utf-8", errors="ignore").strip()
        except Exception as exc:
            logger.warning("Slack file download error", error=str(exc))
            return None
