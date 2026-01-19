"""
ClickUp service for NAVI integration.

Provides sync, query, and write operations for ClickUp workspaces, spaces, and tasks.
"""

from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    SyncResult,
    WriteResult,
)
from backend.integrations.clickup_client import ClickUpClient

logger = structlog.get_logger(__name__)


class ClickUpService(ConnectorServiceBase):
    """
    ClickUp connector service for NAVI.

    Supports:
    - Workspaces (list)
    - Spaces (list)
    - Tasks (list, create, update)
    """

    PROVIDER = "clickup"
    SUPPORTED_ITEM_TYPES = ["workspace", "space", "task"]
    WRITE_OPERATIONS = ["create_task", "update_task", "complete_task"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """Sync workspaces and tasks from ClickUp."""
        logger.info("clickup_service.sync_items.start", connector_id=connection.get("id"))

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(success=False, error="No credentials found")

            access_token = credentials.get("access_token")
            if not access_token:
                return SyncResult(success=False, error="No access token")

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            async with ClickUpClient(access_token) as client:
                workspaces = await client.list_workspaces()

                for workspace in workspaces:
                    ws_id = workspace.get("id")
                    ws_name = workspace.get("name")

                    result = cls.upsert_item(
                        db=db,
                        connector_id=connector_id,
                        item_type="workspace",
                        external_id=ws_id,
                        title=ws_name,
                        status="active",
                        user_id=user_id,
                        org_id=org_id,
                        data={"color": workspace.get("color")},
                    )

                    items_synced += 1
                    if result == "created":
                        items_created += 1
                    else:
                        items_updated += 1

                    # Sync spaces
                    try:
                        spaces = await client.list_spaces(ws_id)
                        for space in spaces:
                            space_id = space.get("id")

                            result = cls.upsert_item(
                                db=db,
                                connector_id=connector_id,
                                item_type="space",
                                external_id=space_id,
                                title=space.get("name"),
                                status="active" if not space.get("archived") else "archived",
                                user_id=user_id,
                                org_id=org_id,
                                data={
                                    "workspace_id": ws_id,
                                    "workspace_name": ws_name,
                                    "private": space.get("private"),
                                },
                            )

                            items_synced += 1
                            if result == "created":
                                items_created += 1
                            else:
                                items_updated += 1

                    except Exception as e:
                        logger.warning("clickup_service.sync_spaces.error", error=str(e))

            cls.update_sync_status(db=db, connector_id=connector_id, status="success")

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("clickup_service.sync_items.error", error=str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        connection: Dict[str, Any],
        action: str,
        data: Dict[str, Any],
    ) -> WriteResult:
        """Perform write operation on ClickUp."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(success=False, error="No credentials found")

            access_token = credentials.get("access_token")
            if not access_token:
                return WriteResult(success=False, error="No access token")

            async with ClickUpClient(access_token) as client:
                if action == "create_task":
                    list_id = data.get("list_id")
                    name = data.get("name")
                    description = data.get("description")

                    if not list_id or not name:
                        return WriteResult(success=False, error="Missing list_id or name")

                    result = await client.create_task(
                        list_id, name, description=description
                    )

                    return WriteResult(
                        success=True,
                        item_id=result.get("id"),
                        url=result.get("url"),
                    )

                return WriteResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("clickup_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    async def list_workspaces(
        cls,
        db: Session,
        connection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """List ClickUp workspaces."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with ClickUpClient(access_token) as client:
                workspaces = await client.list_workspaces()
                return [
                    {
                        "id": ws.get("id"),
                        "name": ws.get("name"),
                        "color": ws.get("color"),
                        "members": len(ws.get("members", [])),
                    }
                    for ws in workspaces
                ]

        except Exception as e:
            logger.error("clickup_service.list_workspaces.error", error=str(e))
            return []

    @classmethod
    async def list_spaces(
        cls,
        db: Session,
        connection: Dict[str, Any],
        workspace_id: str,
    ) -> List[Dict[str, Any]]:
        """List spaces in a ClickUp workspace."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with ClickUpClient(access_token) as client:
                spaces = await client.list_spaces(workspace_id)
                return [
                    {
                        "id": space.get("id"),
                        "name": space.get("name"),
                        "private": space.get("private"),
                        "archived": space.get("archived"),
                    }
                    for space in spaces
                ]

        except Exception as e:
            logger.error("clickup_service.list_spaces.error", error=str(e))
            return []

    @classmethod
    async def list_my_tasks(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List tasks assigned to the current user."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with ClickUpClient(access_token) as client:
                user = await client.get_user()
                user_id = user.get("id")

                # Get tasks from all workspaces
                tasks = []
                workspaces = await client.list_workspaces()

                for ws in workspaces[:3]:  # Limit to 3 workspaces
                    ws_id = ws.get("id")
                    ws_name = ws.get("name")

                    try:
                        spaces = await client.list_spaces(ws_id)
                        for space in spaces[:5]:  # Limit to 5 spaces
                            space_id = space.get("id")

                            try:
                                # Get lists in space
                                lists_resp = await client.client.get(
                                    f"/space/{space_id}/list"
                                )
                                lists_resp.raise_for_status()
                                lists = lists_resp.json().get("lists", [])

                                for lst in lists[:3]:  # Limit to 3 lists
                                    list_id = lst.get("id")
                                    list_name = lst.get("name")

                                    try:
                                        # Get tasks in list
                                        tasks_resp = await client.client.get(
                                            f"/list/{list_id}/task",
                                            params={"assignees[]": [user_id]}
                                        )
                                        tasks_resp.raise_for_status()
                                        list_tasks = tasks_resp.json().get("tasks", [])

                                        for task in list_tasks:
                                            tasks.append({
                                                "id": task.get("id"),
                                                "name": task.get("name"),
                                                "description": task.get("description"),
                                                "status": task.get("status", {}).get("status"),
                                                "url": task.get("url"),
                                                "workspace": ws_name,
                                                "list": list_name,
                                                "due_date": task.get("due_date"),
                                                "priority": task.get("priority"),
                                            })

                                    except Exception:
                                        pass

                            except Exception:
                                pass

                    except Exception:
                        pass

                return tasks[:max_results]

        except Exception as e:
            logger.error("clickup_service.list_my_tasks.error", error=str(e))
            return []
