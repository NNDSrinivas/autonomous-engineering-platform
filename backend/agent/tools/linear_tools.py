"""
Linear tools for NAVI agent.

Provides tools for querying and managing Linear issues, projects, and cycles.
Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, Optional
import logging
import structlog

from backend.services.connector_base import ToolResult

logger = logging.getLogger(__name__)
linear_logger = structlog.get_logger(__name__)


async def list_my_linear_issues(
    context: Dict[str, Any],
    status: Optional[str] = None,
    max_results: int = 20,
) -> "ToolResult":
    """
    List Linear issues assigned to the current user.

    Args:
        context: NAVI context with user info
        status: Optional status filter (e.g., "In Progress", "Done")
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.linear_service import LinearService
    from backend.core.db import get_db

    linear_logger.info(
        "linear_tools.list_my_issues.start",
        status=status,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        user_name = context.get("user_name") or context.get("linear_assignee")

        # Get issues from database
        items = LinearService.list_my_issues(
            db=db,
            user_id=user_id,
            assignee_name=user_name,
            status=status,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"{item.data.get('identifier', item.external_id)}: {item.title[:50] if item.title else 'No title'}",
                "type": "linear",
                "connector": "linear",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Linear issues"
            if user_name:
                output += f" assigned to {user_name}"
            if status:
                output += f" with status '{status}'"
            output += ":\n\n"

            for item in items:
                identifier = item.data.get("identifier", item.external_id)
                output += f"• **{identifier}**: {item.title or 'No title'}\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.data.get("priorityLabel"):
                    output += f"  Priority: {item.data['priorityLabel']}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No Linear issues found"
            if user_name:
                output += f" assigned to {user_name}"
            output += "."

        linear_logger.info(
            "linear_tools.list_my_issues.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        linear_logger.error("linear_tools.list_my_issues.error", error=str(exc))
        return ToolResult(
            output=f"Error retrieving Linear issues: {str(exc)}", sources=[]
        )


async def search_linear_issues(
    context: Dict[str, Any],
    query: str,
    max_results: int = 20,
) -> "ToolResult":
    """
    Search Linear issues by keyword.

    Args:
        context: NAVI context with user info
        query: Search query
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.linear_service import LinearService
    from backend.core.db import get_db

    linear_logger.info(
        "linear_tools.search_issues.start",
        query=query,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Search issues
        items = LinearService.search_issues(
            db=db,
            user_id=user_id,
            query=query,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": f"{item.data.get('identifier', item.external_id)}: {item.title[:50] if item.title else 'No title'}",
                "type": "linear",
                "connector": "linear",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Linear issues matching '{query}':\n\n"

            for item in items:
                identifier = item.data.get("identifier", item.external_id)
                output += f"• **{identifier}**: {item.title or 'No title'}\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.assignee:
                    output += f"  Assignee: {item.assignee}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = f"No Linear issues found matching '{query}'."

        linear_logger.info(
            "linear_tools.search_issues.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        linear_logger.error("linear_tools.search_issues.error", error=str(exc))
        return ToolResult(
            output=f"Error searching Linear issues: {str(exc)}", sources=[]
        )


async def create_linear_issue(
    context: Dict[str, Any],
    team_id: str,
    title: str,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    assignee_id: Optional[str] = None,
    approve: bool = False,
) -> "ToolResult":
    """
    Create a new Linear issue.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        team_id: Linear team ID
        title: Issue title
        description: Issue description (optional)
        priority: Priority 0-4 (optional)
        assignee_id: User ID to assign (optional)
        approve: Must be True to execute

    Returns:
        ToolResult with created issue details
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.linear_service import LinearService
    from backend.core.db import get_db

    linear_logger.info(
        "linear_tools.create_issue.start",
        team_id=team_id,
        title=title,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Create Linear issue\n\n"
            f"• Title: {title}\n"
            f"• Team ID: {team_id}\n"
            f"• Description: {description[:100] + '...' if description and len(description) > 100 else description or 'None'}\n"
            f"• Priority: {priority or 'Default'}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        result = await LinearService.write_item(
            db=db,
            user_id=user_id,
            item_type="issue",
            action="create_issue",
            data={
                "team_id": team_id,
                "title": title,
                "description": description,
                "priority": priority,
                "assignee_id": assignee_id,
            },
            org_id=org_id,
        )

        if result.success:
            sources = []
            if result.url:
                sources.append(
                    {
                        "name": f"{result.external_id}: {title[:50]}",
                        "type": "linear",
                        "connector": "linear",
                        "url": result.url,
                    }
                )

            output = "Successfully created Linear issue:\n\n"
            output += f"• **{result.external_id}**: {title}\n"
            if result.url:
                output += f"• Link: {result.url}\n"

            linear_logger.info(
                "linear_tools.create_issue.done",
                identifier=result.external_id,
            )

            return ToolResult(output=output, sources=sources)
        else:
            return ToolResult(
                output=f"Failed to create Linear issue: {result.error}",
                sources=[],
            )

    except Exception as exc:
        linear_logger.error("linear_tools.create_issue.error", error=str(exc))
        return ToolResult(output=f"Error creating Linear issue: {str(exc)}", sources=[])


async def update_linear_issue_status(
    context: Dict[str, Any],
    issue_id: str,
    state_id: str,
    approve: bool = False,
) -> "ToolResult":
    """
    Update the status of a Linear issue.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        issue_id: Linear issue ID
        state_id: New state ID
        approve: Must be True to execute

    Returns:
        ToolResult with update confirmation
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.linear_service import LinearService
    from backend.core.db import get_db

    linear_logger.info(
        "linear_tools.update_status.start",
        issue_id=issue_id,
        state_id=state_id,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Update Linear issue status\n\n"
            f"• Issue ID: {issue_id}\n"
            f"• New State ID: {state_id}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        result = await LinearService.write_item(
            db=db,
            user_id=user_id,
            item_type="issue",
            action="update_status",
            data={
                "issue_id": issue_id,
                "state_id": state_id,
            },
            org_id=org_id,
        )

        if result.success:
            output = "Successfully updated Linear issue status:\n\n"
            output += f"• Issue: {result.external_id or issue_id}\n"
            if result.data and result.data.get("state"):
                output += f"• New Status: {result.data['state'].get('name')}\n"

            linear_logger.info(
                "linear_tools.update_status.done",
                identifier=result.external_id,
            )

            return ToolResult(output=output, sources=[])
        else:
            return ToolResult(
                output=f"Failed to update Linear issue status: {result.error}",
                sources=[],
            )

    except Exception as exc:
        linear_logger.error("linear_tools.update_status.error", error=str(exc))
        return ToolResult(
            output=f"Error updating Linear issue status: {str(exc)}", sources=[]
        )


async def list_linear_teams(context: Dict[str, Any]) -> "ToolResult":
    """
    List Linear teams accessible to the user.

    Args:
        context: NAVI context with user info

    Returns:
        ToolResult with team list
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.linear_service import LinearService
    from backend.core.db import get_db

    linear_logger.info("linear_tools.list_teams.start")

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        teams = await LinearService.get_teams(db, user_id, org_id)

        if teams:
            output = f"Found {len(teams)} Linear teams:\n\n"
            for team in teams:
                output += f"• **{team.get('key')}**: {team.get('name')}\n"
                output += f"  ID: {team.get('id')}\n"
                output += f"  Issues: {team.get('issueCount', 0)}\n"
                if team.get("description"):
                    output += f"  Description: {team.get('description')[:100]}\n"
                output += "\n"

            linear_logger.info(
                "linear_tools.list_teams.done",
                count=len(teams),
            )

            return ToolResult(output=output, sources=[])
        else:
            return ToolResult(
                output="No Linear teams found. Make sure you have connected Linear.",
                sources=[],
            )

    except Exception as exc:
        linear_logger.error("linear_tools.list_teams.error", error=str(exc))
        return ToolResult(output=f"Error listing Linear teams: {str(exc)}", sources=[])


# Tool function registry for NAVI
LINEAR_TOOLS = {
    "linear.list_my_issues": list_my_linear_issues,
    "linear.search_issues": search_linear_issues,
    "linear.create_issue": create_linear_issue,
    "linear.update_status": update_linear_issue_status,
    "linear.list_teams": list_linear_teams,
}
