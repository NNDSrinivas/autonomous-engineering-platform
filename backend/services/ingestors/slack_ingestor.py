"""
Slack Ingestor - Ingest Slack messages into memory graph

Creates memory nodes for:
- Slack messages
- Slack threads
- Users

Creates edges for:
- message → thread (replies to)
- message → user (mentions)
- message → channel
"""

import logging
from typing import Dict, Any, List, Optional
from backend.services.memory_graph_service import MemoryGraphService

logger = logging.getLogger(__name__)


class SlackIngestor:
    """Ingest Slack messages into the organizational memory graph."""
    
    def __init__(self, memory_service: MemoryGraphService):
        self.mg = memory_service
    
    async def ingest_message(
        self,
        channel_id: str,
        message: Dict[str, Any],
        channel_name: Optional[str] = None
    ) -> int:
        """
        Ingest a Slack message.
        
        Args:
            channel_id: Slack channel ID
            message: Message dict from Slack API
            channel_name: Optional channel name for metadata
            
        Returns:
            Node ID of the created message node
        """
        try:
            text = message.get("text", "")
            user = message.get("user", "Unknown")
            ts = message.get("ts", "")
            thread_ts = message.get("thread_ts")
            
            # Create message node
            node_id = await self.mg.add_node(
                node_type="slack_message",
                text=text,
                title=f"Slack message in #{channel_name or channel_id}",
                meta={
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "user": user,
                    "timestamp": ts,
                    "thread_ts": thread_ts,
                    "is_thread": thread_ts is not None,
                    "url": f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
                }
            )
            
            logger.info(f"Ingested Slack message {ts} as node {node_id}")
            
            # If this is a thread reply, link to parent
            if thread_ts and thread_ts != ts:
                # TODO: Look up parent message node ID
                logger.debug(f"Message {ts} is a reply to thread {thread_ts}")
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to ingest Slack message: {e}", exc_info=True)
            raise
    
    async def link_message_mentions(self, message_node_id: int, mentioned_users: List[str]):
        """
        Create edges for user mentions in a message.
        
        Args:
            message_node_id: Node ID of the message
            mentioned_users: List of user IDs mentioned
        """
        for user_id in mentioned_users:
            # TODO: Look up or create user node
            logger.debug(f"Message {message_node_id} mentions user {user_id}")
