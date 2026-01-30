"""
Jira tools for NAVI agent.

Full CRUD operations for Jira:
- List issues (assigned, by project, by JQL)
- Create issues
- Update issues
- Add comments
- Transition issues
- Search issues

Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, List, Optional
import logging
import structlog

logger = logging.getLogger(__name__)
jira_logger = structlog.get_logger(__name__)


# Jira tool registry
JIRA_TOOLS = {}


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


async def create_jira_issue(
    context: Dict[str, Any],
    project_key: str,
    summary: str,
    description: Optional[str] = None,
    issue_type: str = "Task",
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    approve: bool = False,
):
    """
    Create a new Jira issue.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        project_key: Jira project key (e.g., 'PROJ')
        summary: Issue title/summary
        description: Issue description (supports Jira markdown)
        issue_type: Type of issue (Task, Bug, Story, Epic, etc.)
        priority: Priority level (Highest, High, Medium, Low, Lowest)
        labels: List of labels to add
        assignee: Assignee username or email
        approve: Must be True to execute

    Returns:
        ToolResult with issue details and clickable link
    """
    from backend.agent.tool_executor import ToolResult

    jira_logger.info(
        "jira_tools.create_issue.start",
        project_key=project_key,
        summary=summary,
        issue_type=issue_type,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Create Jira issue\n\n"
            f"• Project: {project_key}\n"
            f"• Summary: {summary}\n"
            f"• Type: {issue_type}\n"
            f"• Priority: {priority or 'Default'}\n"
            f"• Assignee: {assignee or 'Unassigned'}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        from backend.services.jira import JiraService
        from backend.core.db import get_db

        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        # Build issue data
        issue_data = {
            "project_key": project_key,
            "summary": summary,
            "description": description or "",
            "issue_type": issue_type,
        }
        if priority:
            issue_data["priority"] = priority
        if labels:
            issue_data["labels"] = labels
        if assignee:
            issue_data["assignee"] = assignee

        # Create issue via JiraService
        result = await JiraService.create_issue(
            db=db,
            user_id=user_id,
            org_id=org_id,
            **issue_data,
        )

        if result.get("success"):
            issue_key = result.get("issue_key")
            issue_url = result.get("url")

            sources = []
            if issue_url:
                sources.append(
                    {
                        "name": f"{issue_key}: {summary[:50]}",
                        "type": "jira",
                        "connector": "jira",
                        "url": issue_url,
                    }
                )

            jira_logger.info(
                "jira_tools.create_issue.done",
                issue_key=issue_key,
            )

            return ToolResult(
                output=f"✅ Created Jira issue: **{issue_key}**\n\n"
                f"• Summary: {summary}\n"
                f"• Type: {issue_type}\n"
                f"• Link: {issue_url}",
                sources=sources,
            )
        else:
            return ToolResult(
                output=f"❌ Failed to create Jira issue: {result.get('error', 'Unknown error')}",
                sources=[],
            )

    except Exception as exc:
        jira_logger.error("jira_tools.create_issue.error", error=str(exc))
        return ToolResult(output=f"Error creating Jira issue: {str(exc)}", sources=[])


async def update_jira_issue(
    context: Dict[str, Any],
    issue_key: str,
    summary: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    approve: bool = False,
):
    """
    Update an existing Jira issue.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        issue_key: Jira issue key (e.g., 'PROJ-123')
        summary: New summary (optional)
        description: New description (optional)
        status: Transition to new status (e.g., 'In Progress', 'Done')
        priority: New priority (optional)
        labels: New labels (replaces existing)
        assignee: New assignee (optional)
        approve: Must be True to execute

    Returns:
        ToolResult with update confirmation
    """
    from backend.agent.tool_executor import ToolResult

    jira_logger.info(
        "jira_tools.update_issue.start",
        issue_key=issue_key,
        approve=approve,
    )

    # Check approval
    if not approve:
        changes = []
        if summary:
            changes.append(f"• Summary: {summary}")
        if description:
            changes.append("• Description: (updated)")
        if status:
            changes.append(f"• Status: {status}")
        if priority:
            changes.append(f"• Priority: {priority}")
        if labels:
            changes.append(f"• Labels: {', '.join(labels)}")
        if assignee:
            changes.append(f"• Assignee: {assignee}")

        return ToolResult(
            output=f"**Action requires approval**: Update Jira issue {issue_key}\n\n"
            f"Changes:\n" + "\n".join(changes) + "\n\n"
            "Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        from backend.services.jira import JiraService
        from backend.core.db import get_db

        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        # Build update data
        update_data = {}
        if summary:
            update_data["summary"] = summary
        if description:
            update_data["description"] = description
        if priority:
            update_data["priority"] = priority
        if labels:
            update_data["labels"] = labels
        if assignee:
            update_data["assignee"] = assignee

        # Update issue
        result = await JiraService.update_issue(
            db=db,
            user_id=user_id,
            org_id=org_id,
            issue_key=issue_key,
            **update_data,
        )

        # Handle status transition separately if provided
        if status and result.get("success"):
            await JiraService.transition_issue(
                db=db,
                user_id=user_id,
                org_id=org_id,
                issue_key=issue_key,
                status=status,
            )

        if result.get("success"):
            jira_logger.info(
                "jira_tools.update_issue.done",
                issue_key=issue_key,
            )

            return ToolResult(
                output=f"✅ Updated Jira issue: **{issue_key}**",
                sources=[],
            )
        else:
            return ToolResult(
                output=f"❌ Failed to update issue: {result.get('error', 'Unknown error')}",
                sources=[],
            )

    except Exception as exc:
        jira_logger.error("jira_tools.update_issue.error", error=str(exc))
        return ToolResult(output=f"Error updating Jira issue: {str(exc)}", sources=[])


async def add_jira_comment(
    context: Dict[str, Any],
    issue_key: str,
    comment: str,
    approve: bool = False,
):
    """
    Add a comment to a Jira issue.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        issue_key: Jira issue key (e.g., 'PROJ-123')
        comment: Comment text (supports Jira markdown)
        approve: Must be True to execute

    Returns:
        ToolResult with confirmation
    """
    from backend.agent.tool_executor import ToolResult

    jira_logger.info(
        "jira_tools.add_comment.start",
        issue_key=issue_key,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Add comment to {issue_key}\n\n"
            f"Comment:\n{comment[:200]}{'...' if len(comment) > 200 else ''}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        from backend.services.jira import JiraService
        from backend.core.db import get_db

        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        result = await JiraService.add_comment(
            db=db,
            user_id=user_id,
            org_id=org_id,
            issue_key=issue_key,
            body=comment,
        )

        if result.get("success"):
            jira_logger.info(
                "jira_tools.add_comment.done",
                issue_key=issue_key,
            )

            return ToolResult(
                output=f"✅ Added comment to **{issue_key}**",
                sources=[],
            )
        else:
            return ToolResult(
                output=f"❌ Failed to add comment: {result.get('error', 'Unknown error')}",
                sources=[],
            )

    except Exception as exc:
        jira_logger.error("jira_tools.add_comment.error", error=str(exc))
        return ToolResult(output=f"Error adding comment: {str(exc)}", sources=[])


async def search_jira_issues(
    context: Dict[str, Any],
    jql: Optional[str] = None,
    project: Optional[str] = None,
    status: Optional[str] = None,
    text: Optional[str] = None,
    max_results: int = 20,
):
    """
    Search Jira issues using JQL or filters.

    Args:
        context: NAVI context with user info
        jql: Raw JQL query (optional)
        project: Filter by project key (optional)
        status: Filter by status (optional)
        text: Full-text search (optional)
        max_results: Maximum results to return

    Returns:
        ToolResult with matching issues
    """
    from backend.agent.tool_executor import ToolResult

    jira_logger.info(
        "jira_tools.search_issues.start",
        jql=jql,
        project=project,
        status=status,
        text=text,
    )

    try:
        from backend.services.jira import JiraService
        from backend.core.db import get_db

        db = next(get_db())

        # Build JQL if not provided
        if not jql:
            conditions = []
            if project:
                conditions.append(f"project = {project}")
            if status:
                conditions.append(f"status = '{status}'")
            if text:
                conditions.append(f"text ~ '{text}'")
            jql = " AND ".join(conditions) if conditions else "ORDER BY updated DESC"

        issues = JiraService.search_issues(
            db,
            jql=jql,
            limit=max_results,
        )

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

        if issues:
            output = f"Found {len(issues)} Jira issues:\n\n"
            for issue in issues:
                output += (
                    f"• **{issue['issue_key']}**: {issue.get('summary', 'No title')}\n"
                )
                output += f"  Status: {issue.get('status', 'Unknown')}"
                if issue.get("assignee"):
                    output += f" | Assignee: {issue['assignee']}"
                output += f"\n  {issue.get('url', '')}\n\n"
        else:
            output = "No Jira issues found matching your search."

        jira_logger.info(
            "jira_tools.search_issues.done",
            count=len(issues),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        jira_logger.error("jira_tools.search_issues.error", error=str(exc))
        return ToolResult(output=f"Error searching Jira issues: {str(exc)}", sources=[])


# Tool function registry for NAVI
JIRA_TOOLS = {
    "jira_list_assigned": list_assigned_issues_for_user,
    "jira_create_issue": create_jira_issue,
    "jira_update_issue": update_jira_issue,
    "jira_add_comment": add_jira_comment,
    "jira_search": search_jira_issues,
}
