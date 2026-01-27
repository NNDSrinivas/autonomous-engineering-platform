"""
Discord tools for NAVI agent.

Provides tools to query and manage Discord servers, channels, and messages.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_discord_servers(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """
    List Discord servers/guilds the bot is in.

    Args:
        context: Context with user_id and connection info
        max_results: Maximum results to return

    Returns:
        ToolResult with server list and sources
    """
    from backend.services.discord_service import DiscordService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "discord")

        if not connection:
            return ToolResult(
                output="Discord is not connected. Please connect your Discord bot first.",
                sources=[],
            )

        servers = await DiscordService.list_servers(
            db=db,
            connection=connection,
            max_results=max_results,
        )

        if not servers:
            return ToolResult(
                output="No Discord servers found. Make sure the bot has been added to servers.",
                sources=[],
            )

        lines = [f"Found {len(servers)} Discord server(s):\n"]
        sources = []

        for server in servers:
            server_id = server.get("id")
            name = server.get("name", "Unnamed")
            is_owner = "Owner" if server.get("owner") else "Member"

            lines.append(f"- **{name}** (ID: {server_id})")
            lines.append(f"  - Role: {is_owner}")
            lines.append("")

            sources.append(
                {
                    "type": "discord_server",
                    "name": name,
                    "url": f"https://discord.com/channels/{server_id}",
                }
            )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_discord_servers.error", error=str(e))
        return ToolResult(
            output=f"Error listing Discord servers: {e}",
            sources=[],
        )


async def list_discord_channels(
    context: Dict[str, Any],
    guild_id: str,
    channel_type: Optional[str] = None,
    max_results: int = 50,
) -> ToolResult:
    """
    List channels in a Discord server.

    Args:
        context: Context with user_id and connection info
        guild_id: Discord guild/server ID
        channel_type: Filter by type (text, voice, category, etc.)
        max_results: Maximum results to return

    Returns:
        ToolResult with channel list and sources
    """
    from backend.services.discord_service import DiscordService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "discord")

        if not connection:
            return ToolResult(
                output="Discord is not connected. Please connect your Discord bot first.",
                sources=[],
            )

        channels = await DiscordService.list_channels(
            db=db,
            connection=connection,
            guild_id=guild_id,
            channel_type=channel_type,
            max_results=max_results,
        )

        if not channels:
            type_text = f" of type '{channel_type}'" if channel_type else ""
            return ToolResult(
                output=f"No channels found{type_text} in this server.",
                sources=[],
            )

        lines = [f"Found {len(channels)} channel(s):\n"]
        sources = []

        for channel in channels:
            ch_id = channel.get("id")
            name = channel.get("name", "unnamed")
            ch_type = channel.get("type", "unknown")
            topic = channel.get("topic")

            type_emoji = {
                "text": "💬",
                "voice": "🔊",
                "category": "📁",
                "announcement": "📢",
                "forum": "📋",
            }.get(ch_type, "❓")

            lines.append(f"- {type_emoji} **#{name}** ({ch_type})")
            if topic:
                lines.append(f"  - Topic: {topic[:100]}...")
            lines.append(f"  - ID: {ch_id}")
            lines.append("")

            if ch_type == "text":
                sources.append(
                    {
                        "type": "discord_channel",
                        "name": f"#{name}",
                        "url": f"https://discord.com/channels/{guild_id}/{ch_id}",
                    }
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_discord_channels.error", error=str(e))
        return ToolResult(
            output=f"Error listing Discord channels: {e}",
            sources=[],
        )


async def get_discord_messages(
    context: Dict[str, Any],
    channel_id: str,
    max_results: int = 20,
) -> ToolResult:
    """
    Get recent messages from a Discord channel.

    Args:
        context: Context with user_id and connection info
        channel_id: Discord channel ID
        max_results: Maximum results to return

    Returns:
        ToolResult with messages and sources
    """
    from backend.services.discord_service import DiscordService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "discord")

        if not connection:
            return ToolResult(
                output="Discord is not connected. Please connect your Discord bot first.",
                sources=[],
            )

        messages = await DiscordService.get_messages(
            db=db,
            connection=connection,
            channel_id=channel_id,
            max_results=max_results,
        )

        if not messages:
            return ToolResult(
                output="No messages found in this channel.",
                sources=[],
            )

        lines = [f"Recent {len(messages)} message(s):\n"]

        for msg in messages:
            author = msg.get("author", "Unknown")
            content = msg.get("content", "")[:200]
            timestamp = msg.get("timestamp", "")

            lines.append(
                f"**{author}** ({timestamp[:10] if timestamp else 'unknown'}):"
            )
            lines.append(f"> {content}")
            if msg.get("attachments"):
                lines.append(f"  📎 {msg['attachments']} attachment(s)")
            lines.append("")

        sources = [
            {
                "type": "discord_channel",
                "name": f"Channel {channel_id}",
                "url": f"https://discord.com/channels/@me/{channel_id}",
            }
        ]

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_discord_messages.error", error=str(e))
        return ToolResult(
            output=f"Error getting Discord messages: {e}",
            sources=[],
        )


async def send_discord_message(
    context: Dict[str, Any],
    channel_id: str,
    content: str,
    approve: bool = False,
) -> ToolResult:
    """
    Send a message to a Discord channel.

    Args:
        context: Context with user_id and connection info
        channel_id: Discord channel ID
        content: Message content
        approve: Whether to actually execute (requires user approval)

    Returns:
        ToolResult with operation result
    """
    from backend.services.discord_service import DiscordService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(
            output="Error: No user ID in context. Please sign in first.",
            sources=[],
        )

    if not approve:
        return ToolResult(
            output=f"**Preview: Send Discord message**\n\n"
            f"Channel ID: {channel_id}\n"
            f"Message:\n```\n{content}\n```\n\n"
            f"Please approve this action to send the message.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "discord")

        if not connection:
            return ToolResult(
                output="Discord is not connected. Please connect your Discord bot first.",
                sources=[],
            )

        result = await DiscordService.write_item(
            db=db,
            connection=connection,
            action="send_message",
            data={
                "channel_id": channel_id,
                "content": content,
            },
        )

        if result.success:
            return ToolResult(
                output="Message sent successfully to channel.",
                sources=[
                    {
                        "type": "discord_message",
                        "name": "Sent message",
                        "url": result.url
                        or f"https://discord.com/channels/@me/{channel_id}",
                    }
                ],
            )
        else:
            return ToolResult(
                output=f"Failed to send message: {result.error}",
                sources=[],
            )

    except Exception as e:
        logger.error("send_discord_message.error", error=str(e))
        return ToolResult(
            output=f"Error sending message: {e}",
            sources=[],
        )


# Tool registry for the dispatcher
DISCORD_TOOLS = {
    "discord_list_servers": list_discord_servers,
    "discord_list_channels": list_discord_channels,
    "discord_get_messages": get_discord_messages,
    "discord_send_message": send_discord_message,
}
