"""
Jira tools for NAVI agent.

Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, List
import logging
import structlog

logger = logging.getLogger(__name__)
jira_logger = structlog.get_logger(__name__)


async def list_assigned_issues_for_user(context: Dict[str, Any], max_results: int = 20):
    """
    List Jira issues assigned to the current NAVI user.

    Returns ToolResult with clickable Jira issue sources.
    """
    jira_logger.info(
        "jira_tools.list_assigned_issues_for_user.start",
        max_results=max_results,
    )

    try:
        from backend.services.jira import JiraService
        from backend.core.db import get_db

        # Get current user info from context
        current_user_display_name = context.get("jira_assignee") or context.get(
            "user_name"
        )

        issues: List[Dict[str, Any]] = []

        # Use JiraService to get issues from database
        db = next(get_db())

        if current_user_display_name:
            issues = JiraService.list_issues_for_assignee(
                db, assignee=current_user_display_name, limit=max_results
            )
        else:
            # Fallback: get recent issues
            issues = JiraService.search_issues(db, limit=max_results)

        # Build clickable sources for VS Code extension
        sources = [
            {
                "name": f"{issue['issue_key']}: {issue.get('summary', 'No title')[:50]}",
                "type": "jira",
                "connector": "jira",
                "url": issue["url"],
            }
            for issue in issues
            if issue.get("url")
        ]

        # Format output for display
        if issues:
            output = f"Found {len(issues)} Jira issues assigned to you:\n\n"
            for issue in issues:
                output += (
                    f"• **{issue['issue_key']}**: {issue.get('summary', 'No title')}\n"
                )
                output += f"  Status: {issue.get('status', 'Unknown')}\n"
                if issue.get("url"):
                    output += f"  Link: {issue['url']}\n"
                output += "\n"
        else:
            output = "No Jira issues found assigned to you."

        jira_logger.info(
            "jira_tools.list_assigned_issues_for_user.done",
            count=len(issues),
        )

        # Import ToolResult here to avoid circular imports
        from backend.agent.tool_executor import ToolResult

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        jira_logger.error(
            "jira_tools.list_assigned_issues_for_user.error", error=str(exc)
        )

        # Import ToolResult here to avoid circular imports
        from backend.agent.tool_executor import ToolResult

        return ToolResult(
            output=f"Error retrieving Jira issues: {str(exc)}", sources=[]
        )
