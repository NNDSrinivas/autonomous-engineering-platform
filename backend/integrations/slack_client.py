"""Slack client for NAVI memory integration

This client fetches messages, threads, and channel history from Slack
and prepares them for ingestion into NAVI's memory system.
"""

import os
from typing import List, Dict, Any, Optional

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
        try:
            res = self.client.conversations_list(
                exclude_archived=True,
                types="public_channel,private_channel"
            )
            channels = res.get("channels", [])
            logger.info("Listed Slack channels", count=len(channels))
            return channels
        except SlackApiError as e:
            logger.error("Failed to list Slack channels", error=e.response['error'])
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
                channel=channel_id,
                limit=limit,
                oldest=oldest,
                inclusive=False
            )
            messages = res.get("messages", [])
            logger.info("Fetched channel messages", 
                       channel_id=channel_id, 
                       count=len(messages))
            return messages
        except SlackApiError as e:
            logger.error("Failed to fetch channel messages", 
                        channel_id=channel_id,
                        error=e.response['error'])
            raise RuntimeError(f"Slack API error: {e.response['error']}")

    def fetch_thread_replies(
        self, 
        channel_id: str, 
        thread_ts: str
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
            logger.debug("Fetched thread replies",
                        channel_id=channel_id,
                        thread_ts=thread_ts,
                        count=len(messages))
            return messages
        except SlackApiError as e:
            logger.error("Failed to fetch thread replies",
                        channel_id=channel_id,
                        thread_ts=thread_ts,
                        error=e.response['error'])
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
