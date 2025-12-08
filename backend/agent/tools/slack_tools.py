# backend/agent/tools/slack_tools.py

from __future__ import annotations

from typing import Any, Dict

from backend.services.slack_service import search_messages_for_user
from backend.agent.workflow.tool_executor import ToolContext  # adjust import path


async def slack_fetch_recent_channel_messages(
    ctx: ToolContext,
    channel_name: str,
    limit: int = 50,
    last_n_days: int = 1,
) -> Dict[str, Any]:
    """
    Fetch recent Slack messages from channels and return for LLM analysis.

    Args:
        ctx: Tool execution context (db, user_id, etc.)
        channel_name: Slack channel name, e.g. "standup", "#standup"
        limit: Max number of messages
        last_n_days: How far back to look (not used in current implementation)

    Returns:
        Dict with messages list for LLM consumption
    """
    # Use existing slack_service implementation
    messages = search_messages_for_user(
        db=ctx.db,
        user_id=ctx.user_id,
        limit=limit,
        include_threads=True,
    )

    # Filter by channel name if specific channel requested
    if channel_name and channel_name != "all":
        # Simple filtering - in a real implementation you'd want to
        # resolve channel name to ID first
        channel_name_clean = channel_name.lstrip("#").lower()
        filtered_messages = []
        for msg in messages:
            # This is a simple heuristic - the existing implementation
            # would need to be enhanced to include channel names
            if channel_name_clean in str(msg.get("channel", "")).lower():
                filtered_messages.append(msg)
        messages = filtered_messages

    # Return in a format suitable for LLM analysis
    return {
        "channel_filter": channel_name,
        "message_count": len(messages),
        "messages": messages,
        "summary": f"Found {len(messages)} recent Slack messages",
    }


async def slack_search_user_messages(
    ctx: ToolContext,
    limit: int = 30,
) -> Dict[str, Any]:
    """
    Search for recent Slack messages relevant to the current user.

    Args:
        ctx: Tool execution context (db, user_id, etc.)
        limit: Max number of messages to return

    Returns:
        Dict with user's recent Slack activity
    """
    messages = search_messages_for_user(
        db=ctx.db,
        user_id=ctx.user_id,
        limit=limit,
        include_threads=True,
    )

    return {
        "user_id": ctx.user_id,
        "message_count": len(messages),
        "messages": messages,
        "summary": f"Retrieved {len(messages)} recent Slack messages for user {ctx.user_id}",
    }
