"""
ClickUp tools for NAVI agent.

Provides tools to query and manage ClickUp workspaces, spaces, and tasks.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_clickup_workspaces(
    context: Dict[str, Any],
) -> ToolResult:
    """List ClickUp workspaces."""
    from backend.services.clickup_service import ClickUpService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "clickup")

        if not connection:
            return ToolResult(
                output="ClickUp is not connected. Please connect your ClickUp account first.",
                sources=[],
            )

        workspaces = await ClickUpService.list_workspaces(db=db, connection=connection)

        if not workspaces:
            return ToolResult(output="No ClickUp workspaces found.", sources=[])

        lines = [f"Found {len(workspaces)} ClickUp workspace(s):\n"]
        sources = []

        for ws in workspaces:
            name = ws.get("name", "Unnamed")
            ws_id = ws.get("id")
            members = ws.get("members", 0)

            lines.append(f"- **{name}** (ID: {ws_id})")
            lines.append(f"  - Members: {members}")
            lines.append("")

            sources.append({
                "type": "clickup_workspace",
                "name": name,
                "url": f"https://app.clickup.com/{ws_id}",
            })

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_clickup_workspaces.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_clickup_spaces(
    context: Dict[str, Any],
    workspace_id: str,
) -> ToolResult:
    """List spaces in a ClickUp workspace."""
    from backend.services.clickup_service import ClickUpService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "clickup")

        if not connection:
            return ToolResult(output="ClickUp is not connected.", sources=[])

        spaces = await ClickUpService.list_spaces(
            db=db, connection=connection, workspace_id=workspace_id
        )

        if not spaces:
            return ToolResult(output="No spaces found in this workspace.", sources=[])

        lines = [f"Found {len(spaces)} space(s):\n"]
        sources = []

        for space in spaces:
            name = space.get("name", "Unnamed")
            space_id = space.get("id")
            private = "Private" if space.get("private") else "Public"

            lines.append(f"- **{name}** ({private})")
            lines.append(f"  - ID: {space_id}")
            lines.append("")

            sources.append({
                "type": "clickup_space",
                "name": name,
                "url": f"https://app.clickup.com/{workspace_id}/v/s/{space_id}",
            })

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_clickup_spaces.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_my_clickup_tasks(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List ClickUp tasks assigned to the current user."""
    from backend.services.clickup_service import ClickUpService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "clickup")

        if not connection:
            return ToolResult(output="ClickUp is not connected.", sources=[])

        tasks = await ClickUpService.list_my_tasks(
            db=db, connection=connection, max_results=max_results
        )

        if not tasks:
            return ToolResult(output="No ClickUp tasks assigned to you.", sources=[])

        lines = [f"Found {len(tasks)} task(s) assigned to you:\n"]
        sources = []

        for task in tasks:
            name = task.get("name", "Unnamed")
            url = task.get("url", "")
            status = task.get("status", "Unknown")
            workspace = task.get("workspace", "")
            list_name = task.get("list", "")

            lines.append(f"- **{name}**")
            lines.append(f"  - Status: {status}")
            lines.append(f"  - Location: {workspace} > {list_name}")
            if url:
                lines.append(f"  - [Open Task]({url})")
            lines.append("")

            if url:
                sources.append({"type": "clickup_task", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_my_clickup_tasks.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def create_clickup_task(
    context: Dict[str, Any],
    list_id: str,
    name: str,
    description: Optional[str] = None,
    approve: bool = False,
) -> ToolResult:
    """Create a new ClickUp task."""
    from backend.services.clickup_service import ClickUpService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    if not approve:
        return ToolResult(
            output=f"**Preview: Create ClickUp Task**\n\n"
                   f"List ID: {list_id}\n"
                   f"Name: {name}\n"
                   f"Description: {description or 'None'}\n\n"
                   f"Please approve this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "clickup")

        if not connection:
            return ToolResult(output="ClickUp is not connected.", sources=[])

        result = await ClickUpService.write_item(
            db=db,
            connection=connection,
            action="create_task",
            data={"list_id": list_id, "name": name, "description": description},
        )

        if result.success:
            return ToolResult(
                output=f"Task '{name}' created successfully.",
                sources=[{
                    "type": "clickup_task",
                    "name": name,
                    "url": result.url or "",
                }],
            )
        else:
            return ToolResult(output=f"Failed: {result.error}", sources=[])

    except Exception as e:
        logger.error("create_clickup_task.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


CLICKUP_TOOLS = {
    "clickup.list_workspaces": list_clickup_workspaces,
    "clickup.list_spaces": list_clickup_spaces,
    "clickup.list_my_tasks": list_my_clickup_tasks,
    "clickup.create_task": create_clickup_task,
}
