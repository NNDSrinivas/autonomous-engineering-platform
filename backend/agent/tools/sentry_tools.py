"""
Sentry tools for NAVI agent.

Provides tools to query Sentry issues, projects, and error tracking data.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_sentry_issues(
    context: Dict[str, Any],
    project_slug: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 20,
) -> ToolResult:
    """List Sentry issues/errors."""
    from backend.services.sentry_service import SentryService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sentry")

        if not connection:
            return ToolResult(
                output="Sentry is not connected. Please connect your Sentry account first.",
                sources=[],
            )

        issues = await SentryService.list_issues(
            db=db,
            connection=connection,
            project_slug=project_slug,
            query=query,
            max_results=max_results,
        )

        if not issues:
            return ToolResult(output="No Sentry issues found.", sources=[])

        lines = [f"Found {len(issues)} Sentry issue(s):\n"]
        sources = []

        level_emoji = {
            "error": "🔴",
            "warning": "🟠",
            "info": "🔵",
            "debug": "⚪",
        }

        for issue in issues:
            title = issue.get("title", "Unknown Error")[:80]
            level = issue.get("level", "error")
            status = issue.get("status", "unresolved")
            count = issue.get("count", 0)
            user_count = issue.get("user_count", 0)
            project = issue.get("project", "")
            url = issue.get("url", "")
            last_seen = issue.get("last_seen", "")[:10] if issue.get("last_seen") else ""

            emoji = level_emoji.get(level, "⚪")
            status_icon = "✅" if status == "resolved" else "🔄"

            lines.append(f"- {emoji} **{title}**")
            lines.append(f"  - {status_icon} {status.title()} | Events: {count} | Users: {user_count}")
            if project:
                lines.append(f"  - Project: {project}")
            if last_seen:
                lines.append(f"  - Last seen: {last_seen}")
            if url:
                lines.append(f"  - [View in Sentry]({url})")
            lines.append("")

            if url:
                sources.append({"type": "sentry_issue", "name": title[:50], "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_sentry_issues.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_sentry_issue(
    context: Dict[str, Any],
    issue_id: str,
) -> ToolResult:
    """Get detailed information about a Sentry issue."""
    from backend.services.sentry_service import SentryService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sentry")

        if not connection:
            return ToolResult(output="Sentry is not connected.", sources=[])

        issue = await SentryService.get_issue_details(
            db=db, connection=connection, issue_id=issue_id
        )

        if not issue:
            return ToolResult(
                output=f"Could not find Sentry issue with ID {issue_id}.",
                sources=[],
            )

        title = issue.get("title", "Unknown Error")
        culprit = issue.get("culprit", "")
        level = issue.get("level", "error")
        status = issue.get("status", "unresolved")
        count = issue.get("count", 0)
        user_count = issue.get("user_count", 0)
        project = issue.get("project", "")
        url = issue.get("url", "")
        first_seen = issue.get("first_seen", "")[:10] if issue.get("first_seen") else ""
        last_seen = issue.get("last_seen", "")[:10] if issue.get("last_seen") else ""
        assigned_to = issue.get("assignedTo")

        lines = [
            f"# {title}\n",
            f"**Level:** {level.upper()}",
            f"**Status:** {status.title()}",
            f"**Project:** {project}",
            "",
            f"**Events:** {count}",
            f"**Users Affected:** {user_count}",
            "",
            f"**First Seen:** {first_seen}",
            f"**Last Seen:** {last_seen}",
        ]

        if culprit:
            lines.append(f"\n**Culprit:** `{culprit}`")

        if assigned_to:
            lines.append(f"**Assigned To:** {assigned_to.get('name', 'Unknown')}")

        if url:
            lines.append(f"\n[View in Sentry]({url})")

        sources = []
        if url:
            sources.append({"type": "sentry_issue", "name": title[:50], "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_sentry_issue.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_sentry_projects(
    context: Dict[str, Any],
) -> ToolResult:
    """List Sentry projects."""
    from backend.services.sentry_service import SentryService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sentry")

        if not connection:
            return ToolResult(output="Sentry is not connected.", sources=[])

        projects = await SentryService.list_projects(db=db, connection=connection)

        if not projects:
            return ToolResult(output="No Sentry projects found.", sources=[])

        lines = [f"Found {len(projects)} Sentry project(s):\n"]
        sources = []

        for proj in projects:
            name = proj.get("name", "Untitled")
            slug = proj.get("slug", "")
            platform = proj.get("platform", "unknown")
            url = proj.get("url", "")

            lines.append(f"- **{name}** (`{slug}`)")
            lines.append(f"  - Platform: {platform}")
            if url:
                lines.append(f"  - [Open in Sentry]({url})")
            lines.append("")

            if url:
                sources.append({"type": "sentry_project", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_sentry_projects.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def resolve_sentry_issue(
    context: Dict[str, Any],
    issue_id: str,
) -> ToolResult:
    """Mark a Sentry issue as resolved (requires approval)."""
    from backend.services.sentry_service import SentryService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "sentry")

        if not connection:
            return ToolResult(output="Sentry is not connected.", sources=[])

        result = await SentryService.write_item(
            db=db,
            connection=connection,
            operation="resolve_issue",
            issue_id=issue_id,
        )

        if result.get("success"):
            return ToolResult(
                output=f"Issue {issue_id} has been marked as resolved.",
                sources=[],
            )
        else:
            return ToolResult(output="Failed to resolve issue.", sources=[])

    except Exception as e:
        logger.error("resolve_sentry_issue.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


SENTRY_TOOLS = {
    "sentry.list_issues": list_sentry_issues,
    "sentry.get_issue": get_sentry_issue,
    "sentry.list_projects": list_sentry_projects,
    "sentry.resolve_issue": resolve_sentry_issue,
}
