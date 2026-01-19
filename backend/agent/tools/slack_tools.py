"""
Slack tools for NAVI agent.

Provides tools for searching and sending Slack messages.
Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, Optional
import logging
import structlog

logger = logging.getLogger(__name__)
slack_logger = structlog.get_logger(__name__)


async def search_slack_messages(
    context: Dict[str, Any],
    query: str,
    channel: Optional[str] = None,
    max_results: int = 20,
) -> "ToolResult":
    """
    Search Slack messages by keyword.

    Args:
        context: NAVI context with user info
        query: Search query
        channel: Optional channel to filter by
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.slack_service import SlackService
    from backend.core.db import get_db

    slack_logger.info(
        "slack_tools.search_messages.start",
        query=query,
        channel=channel,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Search messages
        items = SlackService.search_messages(
            db=db,
            user_id=user_id,
            query=query,
            channel=channel,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"#{item.data.get('channel_name', 'message')}: {item.title[:30] if item.title else 'Message'}",
                "type": "slack",
                "connector": "slack",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Slack messages matching '{query}'"
            if channel:
                output += f" in #{channel}"
            output += ":\n\n"

            for item in items:
                channel_name = item.data.get("channel_name", "")
                user_name = item.data.get("user_name", "Unknown")
                output += f"• **#{channel_name}** - {user_name}:\n"
                output += f"  {item.title[:200] if item.title else 'No content'}...\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = f"No Slack messages found matching '{query}'"
            if channel:
                output += f" in #{channel}"
            output += "."

        slack_logger.info(
            "slack_tools.search_messages.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        slack_logger.error("slack_tools.search_messages.error", error=str(exc))
        return ToolResult(
            output=f"Error searching Slack messages: {str(exc)}", sources=[]
        )


async def list_slack_channel_messages(
    context: Dict[str, Any],
    channel: str,
    max_results: int = 20,
) -> "ToolResult":
    """
    List recent messages from a Slack channel.

    Args:
        context: NAVI context with user info
        channel: Channel name or ID
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.slack_service import SlackService
    from backend.core.db import get_db

    slack_logger.info(
        "slack_tools.list_channel_messages.start",
        channel=channel,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Get channel messages
        items = SlackService.list_channel_messages(
            db=db,
            user_id=user_id,
            channel=channel,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"{item.data.get('user_name', 'User')}: {item.title[:30] if item.title else 'Message'}",
                "type": "slack",
                "connector": "slack",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} recent messages in #{channel}:\n\n"

            for item in items:
                user_name = item.data.get("user_name", "Unknown")
                timestamp = item.data.get("timestamp", "")
                output += f"• **{user_name}** ({timestamp}):\n"
                output += f"  {item.title[:200] if item.title else 'No content'}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = f"No messages found in #{channel}."

        slack_logger.info(
            "slack_tools.list_channel_messages.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        slack_logger.error("slack_tools.list_channel_messages.error", error=str(exc))
        return ToolResult(
            output=f"Error listing Slack channel messages: {str(exc)}", sources=[]
        )


async def send_slack_message(
    context: Dict[str, Any],
    channel: str,
    message: str,
    thread_ts: Optional[str] = None,
    approve: bool = False,
) -> "ToolResult":
    """
    Send a message to a Slack channel.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        channel: Channel name or ID
        message: Message text to send
        thread_ts: Optional thread timestamp for replies
        approve: Must be True to execute

    Returns:
        ToolResult with send confirmation
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.slack_service import SlackService
    from backend.core.db import get_db

    slack_logger.info(
        "slack_tools.send_message.start",
        channel=channel,
        message_length=len(message),
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Send Slack message\n\n"
            f"• Channel: #{channel}\n"
            f"• Message: {message[:100] + '...' if len(message) > 100 else message}\n"
            f"• Thread: {thread_ts or 'New message'}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        result = await SlackService.send_message(
            db=db,
            user_id=user_id,
            channel=channel,
            message=message,
            thread_ts=thread_ts,
            org_id=org_id,
        )

        if result.success:
            output = f"Successfully sent message to #{channel}"
            if thread_ts:
                output += " (thread reply)"

            slack_logger.info(
                "slack_tools.send_message.done",
                channel=channel,
            )

            return ToolResult(output=output, sources=[])
        else:
            return ToolResult(
                output=f"Failed to send Slack message: {result.error}",
                sources=[],
            )

    except Exception as exc:
        slack_logger.error("slack_tools.send_message.error", error=str(exc))
        return ToolResult(
            output=f"Error sending Slack message: {str(exc)}", sources=[]
        )


# Tool function registry for NAVI
SLACK_TOOLS = {
    "slack.search_messages": search_slack_messages,
    "slack.list_channel_messages": list_slack_channel_messages,
    "slack.send_message": send_slack_message,
}
