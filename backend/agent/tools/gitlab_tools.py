"""
GitLab tools for NAVI agent.

Provides tools for querying GitLab MRs, issues, and pipelines.
Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, Optional
import logging
import structlog

from backend.services.connector_base import ToolResult

logger = logging.getLogger(__name__)
gitlab_logger = structlog.get_logger(__name__)


async def list_my_gitlab_merge_requests(
    context: Dict[str, Any],
    status: Optional[str] = None,
    max_results: int = 20,
) -> "ToolResult":
    """
    List GitLab merge requests assigned to or created by the current user.

    Args:
        context: NAVI context with user info
        status: Optional status filter (opened, closed, merged)
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.gitlab_service import GitLabService
    from backend.core.db import get_db

    gitlab_logger.info(
        "gitlab_tools.list_my_mrs.start",
        status=status,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        user_name = context.get("user_name") or context.get("gitlab_username")

        # Get MRs from database
        items = GitLabService.list_my_merge_requests(
            db=db,
            user_id=user_id,
            assignee_name=user_name,
            status=status,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"!{item.data.get('iid', '')} {item.title[:50] if item.title else 'No title'}",
                "type": "gitlab",
                "connector": "gitlab",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} GitLab merge requests"
            if status:
                output += f" with status '{status}'"
            output += ":\n\n"

            for item in items:
                iid = item.data.get("iid", "")
                project = item.data.get("project_name", "")
                output += f"• **!{iid}** ({project}): {item.title or 'No title'}\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.data.get("source_branch"):
                    output += f"  Branch: {item.data['source_branch']} → {item.data.get('target_branch', 'main')}\n"
                if item.assignee:
                    output += f"  Assignee: {item.assignee}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No GitLab merge requests found"
            if status:
                output += f" with status '{status}'"
            output += "."

        gitlab_logger.info(
            "gitlab_tools.list_my_mrs.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        gitlab_logger.error("gitlab_tools.list_my_mrs.error", error=str(exc))
        return ToolResult(
            output=f"Error retrieving GitLab merge requests: {str(exc)}", sources=[]
        )


async def list_my_gitlab_issues(
    context: Dict[str, Any],
    status: Optional[str] = None,
    max_results: int = 20,
) -> "ToolResult":
    """
    List GitLab issues assigned to the current user.

    Args:
        context: NAVI context with user info
        status: Optional status filter (opened, closed)
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.gitlab_service import GitLabService
    from backend.core.db import get_db

    gitlab_logger.info(
        "gitlab_tools.list_my_issues.start",
        status=status,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        user_name = context.get("user_name") or context.get("gitlab_username")

        # Get issues from database
        items = GitLabService.list_my_issues(
            db=db,
            user_id=user_id,
            assignee_name=user_name,
            status=status,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"#{item.data.get('iid', '')} {item.title[:50] if item.title else 'No title'}",
                "type": "gitlab",
                "connector": "gitlab",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} GitLab issues"
            if status:
                output += f" with status '{status}'"
            output += ":\n\n"

            for item in items:
                iid = item.data.get("iid", "")
                project = item.data.get("project_name", "")
                output += f"• **#{iid}** ({project}): {item.title or 'No title'}\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.assignee:
                    output += f"  Assignee: {item.assignee}\n"
                if item.data.get("labels"):
                    output += f"  Labels: {', '.join(item.data['labels'][:5])}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No GitLab issues found"
            if status:
                output += f" with status '{status}'"
            output += "."

        gitlab_logger.info(
            "gitlab_tools.list_my_issues.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        gitlab_logger.error("gitlab_tools.list_my_issues.error", error=str(exc))
        return ToolResult(
            output=f"Error retrieving GitLab issues: {str(exc)}", sources=[]
        )


async def get_gitlab_pipeline_status(
    context: Dict[str, Any],
    max_results: int = 10,
) -> "ToolResult":
    """
    Get recent GitLab pipeline statuses.

    Args:
        context: NAVI context with user info
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.gitlab_service import GitLabService
    from backend.core.db import get_db

    gitlab_logger.info(
        "gitlab_tools.get_pipeline_status.start",
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Get pipelines from database
        items = GitLabService.get_pipeline_status(
            db=db,
            user_id=user_id,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Pipeline",
                "type": "gitlab",
                "connector": "gitlab",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} recent GitLab pipelines:\n\n"

            for item in items:
                project = item.data.get("project_name", "")
                ref = item.data.get("ref", "")
                status_emoji = {
                    "success": "✓",
                    "failed": "✗",
                    "running": "⟳",
                    "pending": "○",
                    "canceled": "⊘",
                }.get(item.status, "?")

                output += f"• {status_emoji} **{project}** - {ref}\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No GitLab pipelines found."

        gitlab_logger.info(
            "gitlab_tools.get_pipeline_status.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        gitlab_logger.error("gitlab_tools.get_pipeline_status.error", error=str(exc))
        return ToolResult(
            output=f"Error retrieving GitLab pipelines: {str(exc)}", sources=[]
        )


async def search_gitlab(
    context: Dict[str, Any],
    query: str,
    item_type: Optional[str] = None,
    max_results: int = 20,
) -> "ToolResult":
    """
    Search GitLab items (MRs, issues) by keyword.

    Args:
        context: NAVI context with user info
        query: Search query
        item_type: Optional filter (merge_request, issue)
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.gitlab_service import GitLabService
    from backend.core.db import get_db

    gitlab_logger.info(
        "gitlab_tools.search.start",
        query=query,
        item_type=item_type,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Search items
        items = GitLabService.search_items(
            db=db,
            user_id=user_id,
            query=query,
            item_type=item_type,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"{item.item_type}: {item.title[:40] if item.title else 'No title'}",
                "type": "gitlab",
                "connector": "gitlab",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} GitLab items matching '{query}':\n\n"

            for item in items:
                iid = item.data.get("iid", "")
                project = item.data.get("project_name", "")
                type_prefix = "!" if item.item_type == "merge_request" else "#"
                output += f"• **{type_prefix}{iid}** ({project}): {item.title or 'No title'}\n"
                output += (
                    f"  Type: {item.item_type}, Status: {item.status or 'Unknown'}\n"
                )
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = f"No GitLab items found matching '{query}'."

        gitlab_logger.info(
            "gitlab_tools.search.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        gitlab_logger.error("gitlab_tools.search.error", error=str(exc))
        return ToolResult(output=f"Error searching GitLab: {str(exc)}", sources=[])


# Tool function registry for NAVI
GITLAB_TOOLS = {
    "gitlab.list_my_merge_requests": list_my_gitlab_merge_requests,
    "gitlab.list_my_issues": list_my_gitlab_issues,
    "gitlab.get_pipeline_status": get_gitlab_pipeline_status,
    "gitlab.search": search_gitlab,
}
