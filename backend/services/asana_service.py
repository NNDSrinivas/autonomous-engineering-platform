"""
Asana service for NAVI integration.

Provides sync, query, and write operations for Asana tasks and projects.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    ConnectorItem,
    SyncResult,
    WriteResult,
)
from backend.integrations.asana_client import AsanaClient

logger = structlog.get_logger(__name__)


class AsanaService(ConnectorServiceBase):
    """
    Asana connector service for NAVI.

    Supports:
    - Tasks (list, search, create, complete)
    - Projects (list)
    """

    PROVIDER = "asana"
    SUPPORTED_ITEM_TYPES = ["task", "project"]
    WRITE_OPERATIONS = ["create_task", "complete_task", "add_comment"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync tasks and projects from Asana to database.

        Args:
            db: Database session
            connection: Connection with credentials
            item_types: Optional list of types to sync (default: all)

        Returns:
            SyncResult with sync statistics
        """
        logger.info(
            "asana_service.sync_items.start",
            connector_id=connection.get("id"),
            item_types=item_types,
        )

        try:
            # Get credentials
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for Asana connection"
                )

            access_token = credentials.get("access_token")
            if not access_token:
                return SyncResult(
                    success=False, error="No access token in Asana credentials"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            types_to_sync = item_types or ["task", "project"]

            async with AsanaClient(access_token) as client:
                # Get current user
                current_user = await client.get_me()
                user_gid = current_user.get("gid")

                # Get workspaces
                workspaces_data = await client.list_workspaces()
                workspaces = workspaces_data.get("data", [])

                for workspace in workspaces:
                    workspace_gid = workspace.get("gid")
                    workspace_name = workspace.get("name", "")

                    if "project" in types_to_sync:
                        # Fetch projects
                        projects_data = await client.list_projects(
                            workspace_gid=workspace_gid, limit=100
                        )
                        projects = projects_data.get("data", [])

                        for project in projects:
                            external_id = project.get("gid")

                            # Build data dict
                            data = {
                                "workspace_gid": workspace_gid,
                                "workspace_name": workspace_name,
                                "color": project.get("color"),
                                "archived": project.get("archived"),
                            }

                            # Get full project details if needed
                            try:
                                full_project = await client.get_project(external_id)
                                data["notes"] = full_project.get("notes")
                                data["due_on"] = full_project.get("due_on")
                                data["start_on"] = full_project.get("start_on")
                            except Exception:
                                pass

                            result = cls.upsert_item(
                                db=db,
                                connector_id=connector_id,
                                item_type="project",
                                external_id=external_id,
                                title=project.get("name"),
                                url=f"https://app.asana.com/0/{external_id}",
                                user_id=user_id,
                                org_id=org_id,
                                data=data,
                            )

                            if result:
                                items_synced += 1

                        logger.info(
                            "asana_service.sync_items.projects_synced",
                            workspace=workspace_name,
                            count=len(projects),
                        )

                    if "task" in types_to_sync:
                        # Fetch tasks assigned to user
                        try:
                            tasks_data = await client.list_tasks(
                                assignee_gid=user_gid,
                                workspace_gid=workspace_gid,
                                limit=100,
                            )
                            tasks = tasks_data.get("data", [])

                            for task in tasks:
                                external_id = task.get("gid")

                                # Get full task details
                                try:
                                    full_task = await client.get_task(external_id)
                                except Exception:
                                    full_task = task

                                # Determine assignee
                                assignee = None
                                if full_task.get("assignee"):
                                    assignee = full_task["assignee"].get("name")

                                # Parse dates
                                created_at = None
                                updated_at = None
                                if full_task.get("created_at"):
                                    try:
                                        created_at = datetime.fromisoformat(
                                            full_task["created_at"].replace("Z", "+00:00")
                                        )
                                    except Exception:
                                        pass
                                if full_task.get("modified_at"):
                                    try:
                                        updated_at = datetime.fromisoformat(
                                            full_task["modified_at"].replace("Z", "+00:00")
                                        )
                                    except Exception:
                                        pass

                                # Determine status
                                status = "incomplete"
                                if full_task.get("completed"):
                                    status = "completed"

                                # Build data dict
                                data = {
                                    "workspace_gid": workspace_gid,
                                    "workspace_name": workspace_name,
                                    "due_on": full_task.get("due_on"),
                                    "due_at": full_task.get("due_at"),
                                    "projects": full_task.get("projects", []),
                                    "tags": full_task.get("tags", []),
                                    "completed": full_task.get("completed"),
                                    "assignee": full_task.get("assignee"),
                                }

                                result = cls.upsert_item(
                                    db=db,
                                    connector_id=connector_id,
                                    item_type="task",
                                    external_id=external_id,
                                    title=full_task.get("name"),
                                    description=full_task.get("notes"),
                                    status=status,
                                    url=full_task.get("permalink_url") or f"https://app.asana.com/0/{external_id}",
                                    assignee=assignee,
                                    user_id=user_id,
                                    org_id=org_id,
                                    data=data,
                                    external_created_at=created_at,
                                    external_updated_at=updated_at,
                                )

                                if result:
                                    items_synced += 1

                            logger.info(
                                "asana_service.sync_items.tasks_synced",
                                workspace=workspace_name,
                                count=len(tasks),
                            )
                        except Exception as e:
                            logger.warning(
                                "asana_service.sync_items.tasks_error",
                                workspace=workspace_name,
                                error=str(e),
                            )

            # Update connector sync status
            cls.update_sync_status(db, connector_id, "success")

            logger.info(
                "asana_service.sync_items.complete",
                items_synced=items_synced,
            )

            return SyncResult(
                success=True,
                items_synced=items_synced,
            )

        except Exception as e:
            logger.error("asana_service.sync_items.error", error=str(e))
            cls.update_sync_status(db, connection.get("id"), "error", str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        user_id: str,
        item_type: str,
        action: str,
        data: Dict[str, Any],
        org_id: Optional[str] = None,
    ) -> WriteResult:
        """
        Write operation to Asana (create task, complete task).

        Args:
            db: Database session
            user_id: User performing the action
            item_type: Type of item
            action: Action to perform
            data: Data for the operation
            org_id: Optional organization ID

        Returns:
            WriteResult with success status
        """
        logger.info(
            "asana_service.write_item.start",
            user_id=user_id,
            item_type=item_type,
            action=action,
        )

        try:
            # Get connection
            connection = cls.get_connection(db, user_id, org_id)
            if not connection:
                return WriteResult(
                    success=False, error="No Asana connection found for user"
                )

            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(success=False, error="No credentials found")

            access_token = credentials.get("access_token")
            if not access_token:
                return WriteResult(success=False, error="No access token")

            async with AsanaClient(access_token) as client:
                if action == "create_task":
                    name = data.get("name")
                    workspace_gid = data.get("workspace_gid")
                    project_gid = data.get("project_gid")

                    if not name:
                        return WriteResult(
                            success=False, error="name is required for create_task"
                        )

                    if not workspace_gid and not project_gid:
                        return WriteResult(
                            success=False,
                            error="Either workspace_gid or project_gid is required",
                        )

                    projects = [project_gid] if project_gid else None

                    task = await client.create_task(
                        name=name,
                        projects=projects,
                        workspace_gid=workspace_gid,
                        assignee_gid=data.get("assignee_gid"),
                        notes=data.get("notes"),
                        due_on=data.get("due_on"),
                    )

                    logger.info(
                        "asana_service.write_item.task_created",
                        task_gid=task.get("gid"),
                    )

                    return WriteResult(
                        success=True,
                        item_id=task.get("gid"),
                        external_id=task.get("gid"),
                        url=task.get("permalink_url") or f"https://app.asana.com/0/{task.get('gid')}",
                        data=task,
                    )

                elif action == "complete_task":
                    task_gid = data.get("task_gid")
                    if not task_gid:
                        return WriteResult(
                            success=False, error="task_gid is required for complete_task"
                        )

                    task = await client.update_task(task_gid, completed=True)

                    logger.info(
                        "asana_service.write_item.task_completed",
                        task_gid=task_gid,
                    )

                    return WriteResult(
                        success=True,
                        item_id=task.get("gid"),
                        external_id=task.get("gid"),
                        data=task,
                    )

                elif action == "add_comment":
                    task_gid = data.get("task_gid")
                    text = data.get("text")

                    if not task_gid or not text:
                        return WriteResult(
                            success=False,
                            error="task_gid and text are required for add_comment",
                        )

                    story = await client.add_task_comment(task_gid, text)

                    logger.info(
                        "asana_service.write_item.comment_added",
                        task_gid=task_gid,
                    )

                    return WriteResult(
                        success=True,
                        item_id=story.get("gid"),
                        data=story,
                    )

                else:
                    return WriteResult(
                        success=False, error=f"Unknown action: {action}"
                    )

        except Exception as e:
            logger.error("asana_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    def list_my_tasks(
        cls,
        db: Session,
        user_id: str,
        assignee_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List tasks assigned to the user.

        Args:
            db: Database session
            user_id: User ID
            assignee_name: Optional assignee name to filter by
            status: Optional status filter (incomplete, completed)
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="task",
            assignee=assignee_name,
            status=status,
            limit=limit,
        )

    @classmethod
    def search_tasks(
        cls,
        db: Session,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        Search tasks by query.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="task",
            search_query=query,
            limit=limit,
        )

    @classmethod
    def list_projects(
        cls,
        db: Session,
        user_id: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List Asana projects.

        Args:
            db: Database session
            user_id: User ID
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="project",
            limit=limit,
        )
