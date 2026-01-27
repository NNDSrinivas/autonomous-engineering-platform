"""
Figma tools for NAVI agent.

Provides tools to query Figma files, projects, and comments.
"""

from typing import Any, Dict
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_figma_files(
    context: Dict[str, Any],
    project_id: str,
) -> ToolResult:
    """List files in a Figma project."""
    from backend.services.figma_service import FigmaService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "figma")

        if not connection:
            return ToolResult(
                output="Figma is not connected. Please connect your Figma account first.",
                sources=[],
            )

        files = await FigmaService.list_files(
            db=db, connection=connection, project_id=project_id
        )

        if not files:
            return ToolResult(
                output=f"No files found in Figma project {project_id}.",
                sources=[],
            )

        lines = [f"Found {len(files)} file(s) in project:\n"]
        sources = []

        for f in files:
            name = f.get("name", "Untitled")
            url = f.get("url", "")
            last_modified = (
                f.get("last_modified", "")[:10] if f.get("last_modified") else "Unknown"
            )

            lines.append(f"- **{name}**")
            lines.append(f"  - Last Modified: {last_modified}")
            if url:
                lines.append(f"  - [Open in Figma]({url})")
            lines.append("")

            if url:
                sources.append({"type": "figma_file", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_figma_files.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_figma_file(
    context: Dict[str, Any],
    file_key: str,
) -> ToolResult:
    """Get details of a Figma file."""
    from backend.services.figma_service import FigmaService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "figma")

        if not connection:
            return ToolResult(output="Figma is not connected.", sources=[])

        file_data = await FigmaService.get_file(
            db=db, connection=connection, file_key=file_key
        )

        if not file_data:
            return ToolResult(
                output=f"Could not find Figma file with key {file_key}.",
                sources=[],
            )

        name = file_data.get("name", "Untitled")
        url = file_data.get("url", "")
        last_modified = (
            file_data.get("last_modified", "")[:10]
            if file_data.get("last_modified")
            else "Unknown"
        )
        pages = file_data.get("pages", [])

        lines = [
            f"# {name}\n",
            f"**Last Modified:** {last_modified}",
            f"**Version:** {file_data.get('version', 'Unknown')}\n",
        ]

        if pages:
            lines.append("**Pages:**")
            for page in pages:
                lines.append(f"  - {page.get('name', 'Untitled')}")
            lines.append("")

        if url:
            lines.append(f"[Open in Figma]({url})")

        sources = []
        if url:
            sources.append({"type": "figma_file", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_figma_file.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_figma_comments(
    context: Dict[str, Any],
    file_key: str,
) -> ToolResult:
    """Get comments on a Figma file."""
    from backend.services.figma_service import FigmaService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "figma")

        if not connection:
            return ToolResult(output="Figma is not connected.", sources=[])

        comments = await FigmaService.get_comments(
            db=db, connection=connection, file_key=file_key
        )

        if not comments:
            return ToolResult(
                output=f"No comments found on Figma file {file_key}.",
                sources=[],
            )

        lines = [f"Found {len(comments)} comment(s):\n"]

        for c in comments:
            user = c.get("user", "Unknown")
            message = c.get("message", "")
            created = c.get("created_at", "")[:10] if c.get("created_at") else ""
            resolved = c.get("resolved_at")

            status = "✅ Resolved" if resolved else "💬 Open"
            lines.append(f"- {status} **{user}** ({created})")
            lines.append(f"  > {message}")
            lines.append("")

        url = f"https://www.figma.com/file/{file_key}"
        sources = [{"type": "figma_file", "name": f"File {file_key}", "url": url}]

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_figma_comments.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_figma_projects(
    context: Dict[str, Any],
    team_id: str,
) -> ToolResult:
    """List projects in a Figma team."""
    from backend.services.figma_service import FigmaService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "figma")

        if not connection:
            return ToolResult(output="Figma is not connected.", sources=[])

        projects = await FigmaService.list_team_projects(
            db=db, connection=connection, team_id=team_id
        )

        if not projects:
            return ToolResult(
                output=f"No projects found in Figma team {team_id}.",
                sources=[],
            )

        lines = [f"Found {len(projects)} project(s) in team:\n"]
        sources = []

        for p in projects:
            name = p.get("name", "Untitled")
            url = p.get("url", "")
            proj_id = p.get("id", "")

            lines.append(f"- **{name}** (ID: {proj_id})")
            if url:
                lines.append(f"  - [Open in Figma]({url})")
            lines.append("")

            if url:
                sources.append({"type": "figma_project", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_figma_projects.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def add_figma_comment(
    context: Dict[str, Any],
    file_key: str,
    message: str,
) -> ToolResult:
    """Add a comment to a Figma file (requires approval)."""
    from backend.services.figma_service import FigmaService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "figma")

        if not connection:
            return ToolResult(output="Figma is not connected.", sources=[])

        result = await FigmaService.write_item(
            db=db,
            connection=connection,
            operation="post_comment",
            file_key=file_key,
            message=message,
        )

        if result.get("success"):
            url = f"https://www.figma.com/file/{file_key}"
            return ToolResult(
                output=f"Comment added to Figma file.\n\n> {message}\n\n[View file]({url})",
                sources=[
                    {"type": "figma_file", "name": f"File {file_key}", "url": url}
                ],
            )
        else:
            return ToolResult(output="Failed to add comment.", sources=[])

    except Exception as e:
        logger.error("add_figma_comment.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


FIGMA_TOOLS = {
    "figma_list_files": list_figma_files,
    "figma_get_file": get_figma_file,
    "figma_get_comments": get_figma_comments,
    "figma_list_projects": list_figma_projects,
    "figma_add_comment": add_figma_comment,
}
