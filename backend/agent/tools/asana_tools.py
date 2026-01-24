"""
Asana tools for NAVI agent.

Provides tools for querying and managing Asana tasks and projects.
Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, Optional
import logging
import structlog

from backend.services.connector_base import ToolResult

logger = logging.getLogger(__name__)
asana_logger = structlog.get_logger(__name__)


async def list_my_asana_tasks(
    context: Dict[str, Any],
    status: Optional[str] = None,
    max_results: int = 20,
) -> "ToolResult":
    """
    List Asana tasks assigned to the current user.

    Args:
        context: NAVI context with user info
        status: Optional status filter (incomplete, completed)
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.asana_service import AsanaService
    from backend.core.db import get_db

    asana_logger.info(
        "asana_tools.list_my_tasks.start",
        status=status,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        user_name = context.get("user_name")

        # Get tasks from database
        items = AsanaService.list_my_tasks(
            db=db,
            user_id=user_id,
            assignee_name=user_name,
            status=status,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Untitled Task",
                "type": "asana",
                "connector": "asana",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Asana tasks"
            if status:
                output += f" with status '{status}'"
            output += ":\n\n"

            for item in items:
                status_emoji = "✓" if item.status == "completed" else "○"
                output += f"• {status_emoji} **{item.title or 'Untitled Task'}**\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.data.get("due_on"):
                    output += f"  Due: {item.data['due_on']}\n"
                if item.data.get("projects"):
                    project_names = [p.get("name", "") for p in item.data["projects"][:2]]
                    if project_names:
                        output += f"  Projects: {', '.join(project_names)}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No Asana tasks found"
            if status:
                output += f" with status '{status}'"
            output += "."

        asana_logger.info(
            "asana_tools.list_my_tasks.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        asana_logger.error("asana_tools.list_my_tasks.error", error=str(exc))
        return ToolResult(
            output=f"Error retrieving Asana tasks: {str(exc)}", sources=[]
        )


async def search_asana_tasks(
    context: Dict[str, Any],
    query: str,
    max_results: int = 20,
) -> "ToolResult":
    """
    Search Asana tasks by keyword.

    Args:
        context: NAVI context with user info
        query: Search query
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.asana_service import AsanaService
    from backend.core.db import get_db

    asana_logger.info(
        "asana_tools.search_tasks.start",
        query=query,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Search tasks
        items = AsanaService.search_tasks(
            db=db,
            user_id=user_id,
            query=query,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Untitled Task",
                "type": "asana",
                "connector": "asana",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Asana tasks matching '{query}':\n\n"

            for item in items:
                status_emoji = "✓" if item.status == "completed" else "○"
                output += f"• {status_emoji} **{item.title or 'Untitled Task'}**\n"
                output += f"  Status: {item.status or 'Unknown'}\n"
                if item.assignee:
                    output += f"  Assignee: {item.assignee}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = f"No Asana tasks found matching '{query}'."

        asana_logger.info(
            "asana_tools.search_tasks.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        asana_logger.error("asana_tools.search_tasks.error", error=str(exc))
        return ToolResult(
            output=f"Error searching Asana tasks: {str(exc)}", sources=[]
        )


async def list_asana_projects(
    context: Dict[str, Any],
    max_results: int = 20,
) -> "ToolResult":
    """
    List Asana projects.

    Args:
        context: NAVI context with user info
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.asana_service import AsanaService
    from backend.core.db import get_db

    asana_logger.info(
        "asana_tools.list_projects.start",
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Get projects from database
        items = AsanaService.list_projects(
            db=db,
            user_id=user_id,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Untitled Project",
                "type": "asana",
                "connector": "asana",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Asana projects:\n\n"

            for item in items:
                output += f"• **{item.title or 'Untitled Project'}**\n"
                if item.data.get("workspace_name"):
                    output += f"  Workspace: {item.data['workspace_name']}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No Asana projects found. Make sure you have connected Asana."

        asana_logger.info(
            "asana_tools.list_projects.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        asana_logger.error("asana_tools.list_projects.error", error=str(exc))
        return ToolResult(
            output=f"Error listing Asana projects: {str(exc)}", sources=[]
        )


async def create_asana_task(
    context: Dict[str, Any],
    name: str,
    project_gid: Optional[str] = None,
    workspace_gid: Optional[str] = None,
    notes: Optional[str] = None,
    due_on: Optional[str] = None,
    approve: bool = False,
) -> "ToolResult":
    """
    Create a new Asana task.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        name: Task name
        project_gid: Project GID to add task to
        workspace_gid: Workspace GID (if no project)
        notes: Task description
        due_on: Due date (YYYY-MM-DD)
        approve: Must be True to execute

    Returns:
        ToolResult with created task details
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.asana_service import AsanaService
    from backend.core.db import get_db

    asana_logger.info(
        "asana_tools.create_task.start",
        name=name,
        project_gid=project_gid,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Create Asana task\n\n"
            f"• Name: {name}\n"
            f"• Project GID: {project_gid or 'None'}\n"
            f"• Notes: {notes[:100] + '...' if notes and len(notes) > 100 else notes or 'None'}\n"
            f"• Due: {due_on or 'None'}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        result = await AsanaService.write_item(
            db=db,
            user_id=user_id,
            item_type="task",
            action="create_task",
            data={
                "name": name,
                "project_gid": project_gid,
                "workspace_gid": workspace_gid,
                "notes": notes,
                "due_on": due_on,
            },
            org_id=org_id,
        )

        if result.success:
            sources = []
            if result.url:
                sources.append({
                    "name": name[:50],
                    "type": "asana",
                    "connector": "asana",
                    "url": result.url,
                })

            output = "Successfully created Asana task:\n\n"
            output += f"• **{name}**\n"
            if result.url:
                output += f"• Link: {result.url}\n"

            asana_logger.info(
                "asana_tools.create_task.done",
                task_gid=result.item_id,
            )

            return ToolResult(output=output, sources=sources)
        else:
            return ToolResult(
                output=f"Failed to create Asana task: {result.error}",
                sources=[],
            )

    except Exception as exc:
        asana_logger.error("asana_tools.create_task.error", error=str(exc))
        return ToolResult(
            output=f"Error creating Asana task: {str(exc)}", sources=[]
        )


async def complete_asana_task(
    context: Dict[str, Any],
    task_gid: str,
    approve: bool = False,
) -> "ToolResult":
    """
    Mark an Asana task as complete.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        task_gid: Asana task GID
        approve: Must be True to execute

    Returns:
        ToolResult with completion confirmation
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.asana_service import AsanaService
    from backend.core.db import get_db

    asana_logger.info(
        "asana_tools.complete_task.start",
        task_gid=task_gid,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Complete Asana task\n\n"
            f"• Task GID: {task_gid}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        result = await AsanaService.write_item(
            db=db,
            user_id=user_id,
            item_type="task",
            action="complete_task",
            data={"task_gid": task_gid},
            org_id=org_id,
        )

        if result.success:
            output = f"Successfully completed Asana task (GID: {task_gid})"

            asana_logger.info(
                "asana_tools.complete_task.done",
                task_gid=task_gid,
            )

            return ToolResult(output=output, sources=[])
        else:
            return ToolResult(
                output=f"Failed to complete Asana task: {result.error}",
                sources=[],
            )

    except Exception as exc:
        asana_logger.error("asana_tools.complete_task.error", error=str(exc))
        return ToolResult(
            output=f"Error completing Asana task: {str(exc)}", sources=[]
        )


# Tool function registry for NAVI
ASANA_TOOLS = {
    "asana.list_my_tasks": list_my_asana_tasks,
    "asana.search_tasks": search_asana_tasks,
    "asana.list_projects": list_asana_projects,
    "asana.create_task": create_asana_task,
    "asana.complete_task": complete_asana_task,
}
