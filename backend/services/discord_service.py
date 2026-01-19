"""
Discord service for NAVI integration.

Provides sync, query, and write operations for Discord servers, channels, and messages.
"""

from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    SyncResult,
    WriteResult,
)
from backend.integrations.discord_client import DiscordClient

logger = structlog.get_logger(__name__)


class DiscordService(ConnectorServiceBase):
    """
    Discord connector service for NAVI.

    Supports:
    - Guilds/Servers (list)
    - Channels (list, messages)
    - Messages (search, send)
    """

    PROVIDER = "discord"
    SUPPORTED_ITEM_TYPES = ["guild", "channel", "message"]
    WRITE_OPERATIONS = ["send_message"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync guilds and channels from Discord to database.

        Args:
            db: Database session
            connection: Connection with credentials
            item_types: Optional list of types to sync

        Returns:
            SyncResult with sync statistics
        """
        logger.info(
            "discord_service.sync_items.start",
            connector_id=connection.get("id"),
            item_types=item_types,
        )

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for Discord connection"
                )

            bot_token = credentials.get("bot_token") or credentials.get("access_token")
            if not bot_token:
                return SyncResult(
                    success=False, error="No bot token in Discord credentials"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            types_to_sync = item_types or ["guild", "channel"]

            async with DiscordClient(bot_token) as client:
                if "guild" in types_to_sync:
                    guilds = await client.get_current_guilds()

                    for guild in guilds:
                        external_id = guild.get("id", "")

                        data = {
                            "icon": guild.get("icon"),
                            "owner": guild.get("owner"),
                            "permissions": guild.get("permissions"),
                            "features": guild.get("features", []),
                        }

                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="guild",
                            external_id=external_id,
                            title=guild.get("name"),
                            status="active",
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                        )

                        items_synced += 1
                        if result == "created":
                            items_created += 1
                        else:
                            items_updated += 1

                if "channel" in types_to_sync:
                    guilds = await client.get_current_guilds()

                    for guild in guilds[:5]:  # Limit to first 5 guilds
                        guild_id = guild.get("id")
                        guild_name = guild.get("name")

                        try:
                            channels = await client.get_guild_channels(guild_id)

                            for channel in channels:
                                external_id = channel.get("id", "")
                                channel_type = client.get_channel_type_name(
                                    channel.get("type", 0)
                                )

                                data = {
                                    "guild_id": guild_id,
                                    "guild_name": guild_name,
                                    "type": channel_type,
                                    "type_int": channel.get("type"),
                                    "position": channel.get("position"),
                                    "parent_id": channel.get("parent_id"),
                                    "nsfw": channel.get("nsfw", False),
                                }

                                result = cls.upsert_item(
                                    db=db,
                                    connector_id=connector_id,
                                    item_type="channel",
                                    external_id=external_id,
                                    title=channel.get("name"),
                                    description=channel.get("topic"),
                                    status=channel_type,
                                    user_id=user_id,
                                    org_id=org_id,
                                    data=data,
                                )

                                items_synced += 1
                                if result == "created":
                                    items_created += 1
                                else:
                                    items_updated += 1

                        except Exception as e:
                            logger.warning(
                                "discord_service.sync_channels.error",
                                guild_id=guild_id,
                                error=str(e),
                            )

            cls.update_sync_status(
                db=db,
                connector_id=connector_id,
                status="success",
            )

            logger.info(
                "discord_service.sync_items.complete",
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("discord_service.sync_items.error", error=str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        connection: Dict[str, Any],
        action: str,
        data: Dict[str, Any],
    ) -> WriteResult:
        """
        Perform write operation on Discord.

        Args:
            db: Database session
            connection: Connection with credentials
            action: Action to perform (send_message)
            data: Data for the write operation

        Returns:
            WriteResult with operation result
        """
        logger.info(
            "discord_service.write_item.start",
            connector_id=connection.get("id"),
            action=action,
        )

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(
                    success=False, error="No credentials found for Discord connection"
                )

            bot_token = credentials.get("bot_token") or credentials.get("access_token")
            if not bot_token:
                return WriteResult(
                    success=False, error="No bot token in Discord credentials"
                )

            async with DiscordClient(bot_token) as client:
                if action == "send_message":
                    channel_id = data.get("channel_id")
                    content = data.get("content")

                    if not channel_id or not content:
                        return WriteResult(
                            success=False,
                            error="Missing required fields: channel_id, content",
                        )

                    result = await client.send_message(channel_id, content)

                    return WriteResult(
                        success=True,
                        item_id=result.get("id"),
                        url=f"https://discord.com/channels/@me/{channel_id}/{result.get('id')}",
                    )

                else:
                    return WriteResult(
                        success=False, error=f"Unknown action: {action}"
                    )

        except Exception as e:
            logger.error("discord_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    async def list_servers(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Discord servers/guilds the bot is in.

        Args:
            db: Database session
            connection: Connection with credentials
            max_results: Maximum results to return

        Returns:
            List of servers
        """
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            bot_token = credentials.get("bot_token") or credentials.get("access_token")
            if not bot_token:
                return []

            async with DiscordClient(bot_token) as client:
                guilds = await client.get_current_guilds()

                return [
                    {
                        "id": guild.get("id"),
                        "name": guild.get("name"),
                        "icon": guild.get("icon"),
                        "owner": guild.get("owner"),
                        "permissions": guild.get("permissions"),
                    }
                    for guild in guilds[:max_results]
                ]

        except Exception as e:
            logger.error("discord_service.list_servers.error", error=str(e))
            return []

    @classmethod
    async def list_channels(
        cls,
        db: Session,
        connection: Dict[str, Any],
        guild_id: str,
        channel_type: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List channels in a Discord server.

        Args:
            db: Database session
            connection: Connection with credentials
            guild_id: Discord guild/server ID
            channel_type: Filter by type (text, voice, category, etc.)
            max_results: Maximum results to return

        Returns:
            List of channels
        """
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            bot_token = credentials.get("bot_token") or credentials.get("access_token")
            if not bot_token:
                return []

            async with DiscordClient(bot_token) as client:
                channels = await client.get_guild_channels(guild_id)

                result = []
                for channel in channels:
                    ch_type = client.get_channel_type_name(channel.get("type", 0))

                    if channel_type and ch_type != channel_type:
                        continue

                    result.append({
                        "id": channel.get("id"),
                        "name": channel.get("name"),
                        "type": ch_type,
                        "topic": channel.get("topic"),
                        "position": channel.get("position"),
                        "parent_id": channel.get("parent_id"),
                    })

                return result[:max_results]

        except Exception as e:
            logger.error("discord_service.list_channels.error", error=str(e))
            return []

    @classmethod
    async def get_messages(
        cls,
        db: Session,
        connection: Dict[str, Any],
        channel_id: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from a Discord channel.

        Args:
            db: Database session
            connection: Connection with credentials
            channel_id: Discord channel ID
            max_results: Maximum results to return

        Returns:
            List of messages
        """
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            bot_token = credentials.get("bot_token") or credentials.get("access_token")
            if not bot_token:
                return []

            async with DiscordClient(bot_token) as client:
                messages = await client.get_channel_messages(
                    channel_id, limit=max_results
                )

                return [
                    {
                        "id": msg.get("id"),
                        "content": client.extract_message_content(msg),
                        "author": msg.get("author", {}).get("username"),
                        "author_id": msg.get("author", {}).get("id"),
                        "timestamp": msg.get("timestamp"),
                        "attachments": len(msg.get("attachments", [])),
                        "embeds": len(msg.get("embeds", [])),
                    }
                    for msg in messages
                ]

        except Exception as e:
            logger.error("discord_service.get_messages.error", error=str(e))
            return []
