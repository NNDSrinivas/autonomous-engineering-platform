"""
ClickUp API client for project and task management.

Provides access to ClickUp workspaces, spaces, lists, and tasks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class ClickUpClient:
    """
    Async ClickUp API client.

    Supports:
    - Workspace and space management
    - Folder and list operations
    - Task operations
    - Comments and attachments
    - Webhooks
    """

    BASE_URL = "https://api.clickup.com/api/v2"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ClickUpClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": self.access_token,
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    # -------------------------------------------------------------------------
    # User
    # -------------------------------------------------------------------------

    async def get_user(self) -> Dict[str, Any]:
        """Get the authenticated user."""
        resp = await self.client.get("/user")
        resp.raise_for_status()
        return resp.json().get("user", {})

    # -------------------------------------------------------------------------
    # Workspaces (Teams)
    # -------------------------------------------------------------------------

    async def list_workspaces(self) -> List[Dict[str, Any]]:
        """List workspaces (teams) the user belongs to."""
        resp = await self.client.get("/team")
        resp.raise_for_status()
        return resp.json().get("teams", [])

    # -------------------------------------------------------------------------
    # Spaces
    # -------------------------------------------------------------------------

    async def list_spaces(
        self,
        team_id: str,
        archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """List spaces in a workspace."""
        params = {"archived": str(archived).lower()}
        resp = await self.client.get(f"/team/{team_id}/space", params=params)
        resp.raise_for_status()
        return resp.json().get("spaces", [])

    async def get_space(
        self,
        space_id: str,
    ) -> Dict[str, Any]:
        """Get a specific space."""
        resp = await self.client.get(f"/space/{space_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_space(
        self,
        team_id: str,
        name: str,
        multiple_assignees: bool = True,
        features: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a space."""
        payload: Dict[str, Any] = {
            "name": name,
            "multiple_assignees": multiple_assignees,
        }
        if features:
            payload["features"] = features

        resp = await self.client.post(f"/team/{team_id}/space", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_space(
        self,
        space_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
        private: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a space."""
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if color is not None:
            payload["color"] = color
        if private is not None:
            payload["private"] = private

        resp = await self.client.put(f"/space/{space_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_space(
        self,
        space_id: str,
    ) -> Dict[str, Any]:
        """Delete a space."""
        resp = await self.client.delete(f"/space/{space_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Folders
    # -------------------------------------------------------------------------

    async def list_folders(
        self,
        space_id: str,
        archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """List folders in a space."""
        params = {"archived": str(archived).lower()}
        resp = await self.client.get(f"/space/{space_id}/folder", params=params)
        resp.raise_for_status()
        return resp.json().get("folders", [])

    async def get_folder(
        self,
        folder_id: str,
    ) -> Dict[str, Any]:
        """Get a specific folder."""
        resp = await self.client.get(f"/folder/{folder_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_folder(
        self,
        space_id: str,
        name: str,
    ) -> Dict[str, Any]:
        """Create a folder."""
        payload = {"name": name}
        resp = await self.client.post(f"/space/{space_id}/folder", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_folder(
        self,
        folder_id: str,
        name: str,
    ) -> Dict[str, Any]:
        """Update a folder."""
        payload = {"name": name}
        resp = await self.client.put(f"/folder/{folder_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_folder(
        self,
        folder_id: str,
    ) -> Dict[str, Any]:
        """Delete a folder."""
        resp = await self.client.delete(f"/folder/{folder_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Lists
    # -------------------------------------------------------------------------

    async def list_lists(
        self,
        folder_id: Optional[str] = None,
        space_id: Optional[str] = None,
        archived: bool = False,
    ) -> List[Dict[str, Any]]:
        """List lists in a folder or folderless lists in a space."""
        params = {"archived": str(archived).lower()}

        if folder_id:
            url = f"/folder/{folder_id}/list"
        elif space_id:
            url = f"/space/{space_id}/list"
        else:
            raise ValueError("Must provide folder_id or space_id")

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json().get("lists", [])

    async def get_list(
        self,
        list_id: str,
    ) -> Dict[str, Any]:
        """Get a specific list."""
        resp = await self.client.get(f"/list/{list_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_list(
        self,
        folder_id: Optional[str] = None,
        space_id: Optional[str] = None,
        name: str = "",
        content: Optional[str] = None,
        due_date: Optional[int] = None,
        priority: Optional[int] = None,
        assignee: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a list."""
        payload: Dict[str, Any] = {"name": name}
        if content:
            payload["content"] = content
        if due_date:
            payload["due_date"] = due_date
        if priority:
            payload["priority"] = priority
        if assignee:
            payload["assignee"] = assignee
        if status:
            payload["status"] = status

        if folder_id:
            url = f"/folder/{folder_id}/list"
        elif space_id:
            url = f"/space/{space_id}/list"
        else:
            raise ValueError("Must provide folder_id or space_id")

        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_list(
        self,
        list_id: str,
        name: Optional[str] = None,
        content: Optional[str] = None,
        due_date: Optional[int] = None,
        priority: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update a list."""
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if content is not None:
            payload["content"] = content
        if due_date is not None:
            payload["due_date"] = due_date
        if priority is not None:
            payload["priority"] = priority

        resp = await self.client.put(f"/list/{list_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_list(
        self,
        list_id: str,
    ) -> Dict[str, Any]:
        """Delete a list."""
        resp = await self.client.delete(f"/list/{list_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Tasks
    # -------------------------------------------------------------------------

    async def list_tasks(
        self,
        list_id: str,
        archived: bool = False,
        page: int = 0,
        order_by: str = "created",
        reverse: bool = False,
        subtasks: bool = False,
        statuses: Optional[List[str]] = None,
        include_closed: bool = False,
        assignees: Optional[List[str]] = None,
        due_date_gt: Optional[int] = None,
        due_date_lt: Optional[int] = None,
        date_created_gt: Optional[int] = None,
        date_created_lt: Optional[int] = None,
        date_updated_gt: Optional[int] = None,
        date_updated_lt: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List tasks in a list with filters."""
        params: Dict[str, Any] = {
            "archived": str(archived).lower(),
            "page": page,
            "order_by": order_by,
            "reverse": str(reverse).lower(),
            "subtasks": str(subtasks).lower(),
            "include_closed": str(include_closed).lower(),
        }
        if statuses:
            params["statuses[]"] = statuses
        if assignees:
            params["assignees[]"] = assignees
        if due_date_gt:
            params["due_date_gt"] = due_date_gt
        if due_date_lt:
            params["due_date_lt"] = due_date_lt
        if date_created_gt:
            params["date_created_gt"] = date_created_gt
        if date_created_lt:
            params["date_created_lt"] = date_created_lt
        if date_updated_gt:
            params["date_updated_gt"] = date_updated_gt
        if date_updated_lt:
            params["date_updated_lt"] = date_updated_lt

        resp = await self.client.get(f"/list/{list_id}/task", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_task(
        self,
        task_id: str,
        include_subtasks: bool = False,
    ) -> Dict[str, Any]:
        """Get a specific task."""
        params = {"include_subtasks": str(include_subtasks).lower()}
        resp = await self.client.get(f"/task/{task_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_task(
        self,
        list_id: str,
        name: str,
        description: Optional[str] = None,
        assignees: Optional[List[int]] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[int] = None,
        due_date_time: bool = False,
        time_estimate: Optional[int] = None,
        start_date: Optional[int] = None,
        start_date_time: bool = False,
        parent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a task."""
        payload: Dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if assignees:
            payload["assignees"] = assignees
        if tags:
            payload["tags"] = tags
        if status:
            payload["status"] = status
        if priority is not None:
            payload["priority"] = priority
        if due_date:
            payload["due_date"] = due_date
            payload["due_date_time"] = due_date_time
        if time_estimate:
            payload["time_estimate"] = time_estimate
        if start_date:
            payload["start_date"] = start_date
            payload["start_date_time"] = start_date_time
        if parent:
            payload["parent"] = parent

        resp = await self.client.post(f"/list/{list_id}/task", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[int] = None,
        time_estimate: Optional[int] = None,
        assignees: Optional[Dict[str, List[int]]] = None,
        archived: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a task."""
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if status is not None:
            payload["status"] = status
        if priority is not None:
            payload["priority"] = priority
        if due_date is not None:
            payload["due_date"] = due_date
        if time_estimate is not None:
            payload["time_estimate"] = time_estimate
        if assignees is not None:
            payload["assignees"] = assignees
        if archived is not None:
            payload["archived"] = archived

        resp = await self.client.put(f"/task/{task_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_task(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """Delete a task."""
        resp = await self.client.delete(f"/task/{task_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------------

    async def get_task_comments(
        self,
        task_id: str,
    ) -> List[Dict[str, Any]]:
        """Get comments on a task."""
        resp = await self.client.get(f"/task/{task_id}/comment")
        resp.raise_for_status()
        return resp.json().get("comments", [])

    async def create_task_comment(
        self,
        task_id: str,
        comment_text: str,
        assignee: Optional[int] = None,
        notify_all: bool = True,
    ) -> Dict[str, Any]:
        """Create a comment on a task."""
        payload: Dict[str, Any] = {
            "comment_text": comment_text,
            "notify_all": notify_all,
        }
        if assignee:
            payload["assignee"] = assignee

        resp = await self.client.post(f"/task/{task_id}/comment", json=payload)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Time Tracking
    # -------------------------------------------------------------------------

    async def get_time_entries(
        self,
        team_id: str,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
        assignee: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get time entries."""
        params: Dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if assignee:
            params["assignee"] = assignee

        resp = await self.client.get(f"/team/{team_id}/time_entries", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_time_entry(
        self,
        task_id: str,
        start: int,
        end: Optional[int] = None,
        duration: Optional[int] = None,
        description: Optional[str] = None,
        billable: bool = False,
    ) -> Dict[str, Any]:
        """Create a time entry."""
        payload: Dict[str, Any] = {
            "start": start,
            "billable": billable,
        }
        if end:
            payload["end"] = end
        if duration:
            payload["duration"] = duration
        if description:
            payload["description"] = description

        resp = await self.client.post(f"/task/{task_id}/time", json=payload)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    async def get_space_tags(
        self,
        space_id: str,
    ) -> List[Dict[str, Any]]:
        """Get tags for a space."""
        resp = await self.client.get(f"/space/{space_id}/tag")
        resp.raise_for_status()
        return resp.json().get("tags", [])

    async def create_space_tag(
        self,
        space_id: str,
        name: str,
        tag_fg: str = "#FFFFFF",
        tag_bg: str = "#7B68EE",
    ) -> Dict[str, Any]:
        """Create a tag in a space."""
        payload = {
            "tag": {
                "name": name,
                "tag_fg": tag_fg,
                "tag_bg": tag_bg,
            }
        }
        resp = await self.client.post(f"/space/{space_id}/tag", json=payload)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        team_id: str,
    ) -> Dict[str, Any]:
        """List webhooks for a workspace."""
        resp = await self.client.get(f"/team/{team_id}/webhook")
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        team_id: str,
        endpoint: str,
        events: List[str],
        space_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        list_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            team_id: Workspace ID
            endpoint: Webhook URL
            events: Event types (taskCreated, taskUpdated, taskDeleted, etc.)
            space_id: Filter to specific space
            folder_id: Filter to specific folder
            list_id: Filter to specific list
            task_id: Filter to specific task

        Returns:
            Created webhook
        """
        payload: Dict[str, Any] = {
            "endpoint": endpoint,
            "events": events,
        }
        if space_id:
            payload["space_id"] = space_id
        if folder_id:
            payload["folder_id"] = folder_id
        if list_id:
            payload["list_id"] = list_id
        if task_id:
            payload["task_id"] = task_id

        resp = await self.client.post(f"/team/{team_id}/webhook", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_webhook(
        self,
        webhook_id: str,
        endpoint: Optional[str] = None,
        events: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a webhook."""
        payload: Dict[str, Any] = {}
        if endpoint:
            payload["endpoint"] = endpoint
        if events:
            payload["events"] = events
        if status:
            payload["status"] = status

        resp = await self.client.put(f"/webhook/{webhook_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(
        self,
        webhook_id: str,
    ) -> Dict[str, Any]:
        """Delete a webhook."""
        resp = await self.client.delete(f"/webhook/{webhook_id}")
        resp.raise_for_status()
        return resp.json()
