"""
Slack connector service for AEP NAVI integration.

Provides methods for syncing and querying Slack data, as well as
write operations like sending messages.
"""

from typing import Any, Dict, List, Optional
import logging
import structlog

from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    ConnectorItem,
    SyncResult,
    WriteResult,
)

logger = logging.getLogger(__name__)
slack_logger = structlog.get_logger(__name__)


class SlackService(ConnectorServiceBase):
    """Slack connector service implementation."""

    PROVIDER = "slack"

    @classmethod
    async def sync_items(
        cls, db: Session, connection, item_types: List[str]
    ) -> SyncResult:
        """
        Sync messages and channels from Slack.

        Args:
            db: Database session
            connection: Connector record with credentials
            item_types: Types to sync (messages, channels)

        Returns:
            SyncResult with counts and any errors
        """
        from backend.integrations.slack_client import SlackClient
        from backend.core.crypto import decrypt_token

        slack_logger.info(
            "slack_service.sync_items.start",
            connector_id=connection.id,
            item_types=item_types,
        )

        synced = 0
        errors = []

        try:
            # Get token from connector secrets
            secrets = connection.secrets or {}
            token = secrets.get("bot_token")
            if token:
                token = decrypt_token(token)

            if not token:
                return SyncResult(
                    success=False,
                    synced_count=0,
                    errors=["No Slack bot token found"],
                )

            client = SlackClient(bot_token=token)

            # Sync channels if requested
            if "channels" in item_types or "channel" in item_types:
                try:
                    channels = client.list_channels()
                    for channel in channels:
                        cls.upsert_item(
                            db=db,
                            connector_id=connection.id,
                            item_type="channel",
                            external_id=channel.get("id", ""),
                            title=channel.get("name", ""),
                            status="active" if not channel.get("is_archived") else "archived",
                            data={
                                "name": channel.get("name"),
                                "topic": channel.get("topic", {}).get("value"),
                                "purpose": channel.get("purpose", {}).get("value"),
                                "is_private": channel.get("is_private", False),
                                "num_members": channel.get("num_members", 0),
                            },
                            user_id=connection.user_id,
                            org_id=connection.org_id,
                        )
                        synced += 1
                except Exception as e:
                    errors.append(f"Error syncing channels: {str(e)}")

            # Sync recent messages if requested
            if "messages" in item_types or "message" in item_types:
                try:
                    channels = client.list_channels()
                    for channel in channels[:10]:  # Limit to 10 channels
                        ch_id = channel.get("id")
                        ch_name = channel.get("name", ch_id)
                        if not ch_id:
                            continue

                        messages = client.fetch_channel_messages(
                            channel_id=ch_id,
                            limit=50,
                        )

                        for msg in messages or []:
                            ts = msg.get("ts")
                            if not ts:
                                continue

                            permalink = f"https://slack.com/archives/{ch_id}/p{ts.replace('.', '')}"

                            cls.upsert_item(
                                db=db,
                                connector_id=connection.id,
                                item_type="message",
                                external_id=f"{ch_id}:{ts}",
                                title=msg.get("text", "")[:500],
                                url=permalink,
                                data={
                                    "channel_id": ch_id,
                                    "channel_name": ch_name,
                                    "user_id": msg.get("user"),
                                    "timestamp": ts,
                                    "thread_ts": msg.get("thread_ts"),
                                    "reactions": msg.get("reactions", []),
                                },
                                user_id=connection.user_id,
                                org_id=connection.org_id,
                            )
                            synced += 1
                except Exception as e:
                    errors.append(f"Error syncing messages: {str(e)}")

            db.commit()

            slack_logger.info(
                "slack_service.sync_items.done",
                synced=synced,
                errors=len(errors),
            )

            return SyncResult(
                success=len(errors) == 0,
                synced_count=synced,
                errors=errors if errors else None,
            )

        except Exception as exc:
            slack_logger.error("slack_service.sync_items.error", error=str(exc))
            return SyncResult(
                success=False,
                synced_count=synced,
                errors=[str(exc)],
            )

    @classmethod
    async def write_item(
        cls,
        db: Session,
        user_id: str,
        item_type: str,
        action: str,
        data: Dict[str, Any],
        org_id: Optional[str] = None,
    ) -> WriteResult:
        """
        Write operations for Slack (send message, etc.).

        Args:
            db: Database session
            user_id: User performing the action
            item_type: Type of item (message)
            action: Action to perform (send_message)
            data: Action-specific data
            org_id: Optional organization ID

        Returns:
            WriteResult with success status
        """
        from backend.integrations.slack_client import SlackClient
        from backend.core.crypto import decrypt_token

        slack_logger.info(
            "slack_service.write_item.start",
            user_id=user_id,
            item_type=item_type,
            action=action,
        )

        try:
            connection = cls.get_connection(db, user_id, org_id)
            if not connection:
                return WriteResult(
                    success=False,
                    error="No Slack connection found. Please connect Slack first.",
                )

            # Get token from connector secrets
            secrets = connection.secrets or {}
            token = secrets.get("bot_token")
            if token:
                token = decrypt_token(token)

            if not token:
                return WriteResult(
                    success=False,
                    error="No Slack bot token found",
                )

            client = SlackClient(bot_token=token)

            if action == "send_message":
                channel = data.get("channel")
                message = data.get("message")
                thread_ts = data.get("thread_ts")

                if not channel or not message:
                    return WriteResult(
                        success=False,
                        error="Channel and message are required",
                    )

                result = client.send_message(
                    channel=channel,
                    text=message,
                    thread_ts=thread_ts,
                )

                if result:
                    return WriteResult(
                        success=True,
                        item_id=result.get("ts"),
                        data=result,
                    )
                else:
                    return WriteResult(
                        success=False,
                        error="Failed to send message",
                    )
            else:
                return WriteResult(
                    success=False,
                    error=f"Unknown action: {action}",
                )

        except Exception as exc:
            slack_logger.error("slack_service.write_item.error", error=str(exc))
            return WriteResult(
                success=False,
                error=str(exc),
            )

    # -------------------------------------------------------------------------
    # Helper methods for NAVI tools
    # -------------------------------------------------------------------------

    @classmethod
    def search_messages(
        cls,
        db: Session,
        user_id: str,
        query: str,
        channel: Optional[str] = None,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        Search Slack messages by query.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            channel: Optional channel filter
            limit: Maximum results

        Returns:
            List of ConnectorItem results
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            org_id=None,
            item_type="message",
            search_query=query,
            limit=limit,
        )

    @classmethod
    def list_channel_messages(
        cls,
        db: Session,
        user_id: str,
        channel: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List messages from a specific channel.

        Args:
            db: Database session
            user_id: User ID
            channel: Channel name or ID
            limit: Maximum results

        Returns:
            List of ConnectorItem results
        """
        # Get items and filter by channel
        items = cls.get_items(
            db=db,
            user_id=user_id,
            org_id=None,
            item_type="message",
            limit=limit * 3,  # Fetch more to filter
        )

        # Filter by channel
        filtered = []
        for item in items:
            ch_name = item.data.get("channel_name", "")
            ch_id = item.data.get("channel_id", "")
            if channel.lower() in ch_name.lower() or channel == ch_id:
                filtered.append(item)
                if len(filtered) >= limit:
                    break

        return filtered

    @classmethod
    async def send_message(
        cls,
        db: Session,
        user_id: str,
        channel: str,
        message: str,
        thread_ts: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> WriteResult:
        """
        Send a message to a Slack channel.

        Args:
            db: Database session
            user_id: User ID
            channel: Channel name or ID
            message: Message text
            thread_ts: Optional thread timestamp
            org_id: Optional organization ID

        Returns:
            WriteResult with success status
        """
        return await cls.write_item(
            db=db,
            user_id=user_id,
            item_type="message",
            action="send_message",
            data={
                "channel": channel,
                "message": message,
                "thread_ts": thread_ts,
            },
            org_id=org_id,
        )


# -------------------------------------------------------------------------
# Legacy functions for backward compatibility
# -------------------------------------------------------------------------


def search_messages_for_user(
    db: Session,
    user_id: str,
    limit: int = 30,
    include_threads: bool = True,
) -> List[Dict[str, Any]]:
    """
    Legacy function for backward compatibility.
    Return recent Slack messages for the given user.
    """
    from backend.integrations.slack_client import SlackClient
    from backend.services import connectors as connectors_service

    try:
        token = None
        connector = connectors_service.get_connector_for_context(
            db, user_id=user_id, org_id=None, provider="slack"
        )
        if connector:
            token = (connector.get("secrets") or {}).get("bot_token")

        client = SlackClient(bot_token=token) if token else SlackClient()
    except Exception as e:
        logger.info("SlackClient not available: %s", e)
        return []

    messages: List[Dict[str, Any]] = []

    try:
        channels = client.list_channels()
    except Exception as e:
        logger.warning("Slack: failed to list channels: %s", e, exc_info=True)
        return []

    for ch in channels:
        if len(messages) >= limit:
            break

        ch_id = ch.get("id")
        ch_name = ch.get("name") or ch_id
        if not ch_id:
            continue

        try:
            raw_msgs = client.fetch_channel_messages(
                channel_id=ch_id,
                limit=min(limit - len(messages), 200),
            )
        except Exception as e:
            logger.warning(
                "Slack: failed to fetch messages for channel %s: %s",
                ch_id,
                e,
                exc_info=True,
            )
            continue

        for m in raw_msgs or []:
            if len(messages) >= limit:
                break

            ts = m.get("ts")
            text = m.get("text") or ""
            user = m.get("user")

            messages.append(
                {
                    "id": f"{ch_id}:{ts}",
                    "channel": ch_id,
                    "channel_name": ch_name,
                    "text": text,
                    "user": user,
                    "ts": ts,
                    "permalink": f"https://slack.com/archives/{ch_id}/p{ts.replace('.', '')}" if ts else None,
                }
            )

    logger.info("Slack: collected %d messages for org memory", len(messages))
    return messages


def search_messages(
    db: Session,
    user_id: str,
    query: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Legacy function for backward compatibility.
    Search Slack messages by query text.
    """
    return search_messages_for_user(db, user_id, limit, include_threads=True)
