"""
Asana API client for project and task management.

Provides access to Asana workspaces, projects, tasks, and users.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class AsanaClient:
    """
    Async Asana API client.

    Supports:
    - Workspace and project management
    - Task operations
    - User and team management
    - Custom fields
    - Webhooks
    """

    BASE_URL = "https://app.asana.com/api/1.0"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AsanaClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.access_token}",
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
    # Users
    # -------------------------------------------------------------------------

    async def get_me(self) -> Dict[str, Any]:
        """Get the authenticated user."""
        resp = await self.client.get("/users/me")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_user(
        self,
        user_gid: str,
    ) -> Dict[str, Any]:
        """Get a specific user."""
        resp = await self.client.get(f"/users/{user_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def list_users_in_workspace(
        self,
        workspace_gid: str,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List users in a workspace."""
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset

        resp = await self.client.get(
            f"/workspaces/{workspace_gid}/users",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Workspaces
    # -------------------------------------------------------------------------

    async def list_workspaces(
        self,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List accessible workspaces."""
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset

        resp = await self.client.get("/workspaces", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_workspace(
        self,
        workspace_gid: str,
    ) -> Dict[str, Any]:
        """Get a specific workspace."""
        resp = await self.client.get(f"/workspaces/{workspace_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def list_projects(
        self,
        workspace_gid: Optional[str] = None,
        team_gid: Optional[str] = None,
        archived: bool = False,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List projects.

        Args:
            workspace_gid: Filter by workspace
            team_gid: Filter by team
            archived: Include archived projects
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of projects
        """
        params: Dict[str, Any] = {
            "limit": limit,
            "archived": str(archived).lower(),
        }
        if offset:
            params["offset"] = offset

        if team_gid:
            url = f"/teams/{team_gid}/projects"
        elif workspace_gid:
            url = f"/workspaces/{workspace_gid}/projects"
        else:
            url = "/projects"

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_project(
        self,
        project_gid: str,
    ) -> Dict[str, Any]:
        """Get a specific project."""
        resp = await self.client.get(f"/projects/{project_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def create_project(
        self,
        workspace_gid: str,
        name: str,
        team_gid: Optional[str] = None,
        notes: Optional[str] = None,
        color: Optional[str] = None,
        default_view: str = "list",
        public: bool = False,
    ) -> Dict[str, Any]:
        """Create a project."""
        payload: Dict[str, Any] = {
            "data": {
                "workspace": workspace_gid,
                "name": name,
                "default_view": default_view,
                "public": public,
            }
        }
        if team_gid:
            payload["data"]["team"] = team_gid
        if notes:
            payload["data"]["notes"] = notes
        if color:
            payload["data"]["color"] = color

        resp = await self.client.post("/projects", json=payload)
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def update_project(
        self,
        project_gid: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        color: Optional[str] = None,
        archived: Optional[bool] = None,
        public: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a project."""
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if notes is not None:
            data["notes"] = notes
        if color is not None:
            data["color"] = color
        if archived is not None:
            data["archived"] = archived
        if public is not None:
            data["public"] = public

        resp = await self.client.put(f"/projects/{project_gid}", json={"data": data})
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def delete_project(
        self,
        project_gid: str,
    ) -> Dict[str, Any]:
        """Delete a project."""
        resp = await self.client.delete(f"/projects/{project_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Tasks
    # -------------------------------------------------------------------------

    async def list_tasks(
        self,
        project_gid: Optional[str] = None,
        section_gid: Optional[str] = None,
        assignee_gid: Optional[str] = None,
        workspace_gid: Optional[str] = None,
        completed_since: Optional[str] = None,
        modified_since: Optional[str] = None,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List tasks.

        Args:
            project_gid: Filter by project
            section_gid: Filter by section
            assignee_gid: Filter by assignee (requires workspace)
            workspace_gid: Workspace for assignee filter
            completed_since: Only incomplete or completed after date
            modified_since: Only modified after date
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of tasks
        """
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset
        if completed_since:
            params["completed_since"] = completed_since
        if modified_since:
            params["modified_since"] = modified_since

        if project_gid:
            url = f"/projects/{project_gid}/tasks"
        elif section_gid:
            url = f"/sections/{section_gid}/tasks"
        elif assignee_gid and workspace_gid:
            url = "/tasks"
            params["assignee"] = assignee_gid
            params["workspace"] = workspace_gid
        else:
            raise ValueError(
                "Must provide project_gid, section_gid, or assignee_gid+workspace_gid"
            )

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_task(
        self,
        task_gid: str,
    ) -> Dict[str, Any]:
        """Get a specific task."""
        resp = await self.client.get(f"/tasks/{task_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def create_task(
        self,
        name: str,
        projects: Optional[List[str]] = None,
        workspace_gid: Optional[str] = None,
        assignee_gid: Optional[str] = None,
        notes: Optional[str] = None,
        due_on: Optional[str] = None,
        due_at: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parent_gid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a task.

        Args:
            name: Task name
            projects: Project GIDs to add task to
            workspace_gid: Workspace (required if no projects)
            assignee_gid: Assignee user GID
            notes: Task description
            due_on: Due date (YYYY-MM-DD)
            due_at: Due datetime (ISO 8601)
            tags: Tag GIDs
            parent_gid: Parent task GID (for subtasks)

        Returns:
            Created task
        """
        data: Dict[str, Any] = {"name": name}

        if projects:
            data["projects"] = projects
        elif workspace_gid:
            data["workspace"] = workspace_gid
        else:
            raise ValueError("Must provide projects or workspace_gid")

        if assignee_gid:
            data["assignee"] = assignee_gid
        if notes:
            data["notes"] = notes
        if due_on:
            data["due_on"] = due_on
        if due_at:
            data["due_at"] = due_at
        if tags:
            data["tags"] = tags
        if parent_gid:
            data["parent"] = parent_gid

        resp = await self.client.post("/tasks", json={"data": data})
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def update_task(
        self,
        task_gid: str,
        name: Optional[str] = None,
        assignee_gid: Optional[str] = None,
        notes: Optional[str] = None,
        due_on: Optional[str] = None,
        due_at: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a task."""
        data: Dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if assignee_gid is not None:
            data["assignee"] = assignee_gid
        if notes is not None:
            data["notes"] = notes
        if due_on is not None:
            data["due_on"] = due_on
        if due_at is not None:
            data["due_at"] = due_at
        if completed is not None:
            data["completed"] = completed

        resp = await self.client.put(f"/tasks/{task_gid}", json={"data": data})
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def delete_task(
        self,
        task_gid: str,
    ) -> Dict[str, Any]:
        """Delete a task."""
        resp = await self.client.delete(f"/tasks/{task_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def add_task_to_project(
        self,
        task_gid: str,
        project_gid: str,
        section_gid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a task to a project."""
        data: Dict[str, Any] = {"project": project_gid}
        if section_gid:
            data["section"] = section_gid

        resp = await self.client.post(
            f"/tasks/{task_gid}/addProject",
            json={"data": data},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def remove_task_from_project(
        self,
        task_gid: str,
        project_gid: str,
    ) -> Dict[str, Any]:
        """Remove a task from a project."""
        resp = await self.client.post(
            f"/tasks/{task_gid}/removeProject",
            json={"data": {"project": project_gid}},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_task_stories(
        self,
        task_gid: str,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get stories (comments/history) for a task."""
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset

        resp = await self.client.get(f"/tasks/{task_gid}/stories", params=params)
        resp.raise_for_status()
        return resp.json()

    async def add_task_comment(
        self,
        task_gid: str,
        text: str,
    ) -> Dict[str, Any]:
        """Add a comment to a task."""
        resp = await self.client.post(
            f"/tasks/{task_gid}/stories",
            json={"data": {"text": text}},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Sections
    # -------------------------------------------------------------------------

    async def list_sections(
        self,
        project_gid: str,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List sections in a project."""
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset

        resp = await self.client.get(f"/projects/{project_gid}/sections", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_section(
        self,
        project_gid: str,
        name: str,
    ) -> Dict[str, Any]:
        """Create a section in a project."""
        resp = await self.client.post(
            f"/projects/{project_gid}/sections",
            json={"data": {"name": name}},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    async def list_tags(
        self,
        workspace_gid: str,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List tags in a workspace."""
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset

        resp = await self.client.get(f"/workspaces/{workspace_gid}/tags", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_tag(
        self,
        workspace_gid: str,
        name: str,
        color: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a tag."""
        data: Dict[str, Any] = {"workspace": workspace_gid, "name": name}
        if color:
            data["color"] = color

        resp = await self.client.post("/tags", json={"data": data})
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Teams
    # -------------------------------------------------------------------------

    async def list_teams(
        self,
        workspace_gid: str,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List teams in a workspace."""
        params: Dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset

        resp = await self.client.get(
            f"/workspaces/{workspace_gid}/teams", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def get_team(
        self,
        team_gid: str,
    ) -> Dict[str, Any]:
        """Get a specific team."""
        resp = await self.client.get(f"/teams/{team_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        workspace_gid: str,
        resource_gid: Optional[str] = None,
        limit: int = 100,
        offset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List webhooks."""
        params: Dict[str, Any] = {
            "workspace": workspace_gid,
            "limit": limit,
        }
        if resource_gid:
            params["resource"] = resource_gid
        if offset:
            params["offset"] = offset

        resp = await self.client.get("/webhooks", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        resource_gid: str,
        target: str,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            resource_gid: Resource to watch (project, task, etc.)
            target: Webhook URL
            filters: Event filters

        Returns:
            Created webhook
        """
        data: Dict[str, Any] = {
            "resource": resource_gid,
            "target": target,
        }
        if filters:
            data["filters"] = filters

        resp = await self.client.post("/webhooks", json={"data": data})
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def delete_webhook(
        self,
        webhook_gid: str,
    ) -> Dict[str, Any]:
        """Delete a webhook."""
        resp = await self.client.delete(f"/webhooks/{webhook_gid}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search_tasks(
        self,
        workspace_gid: str,
        text: Optional[str] = None,
        projects_any: Optional[List[str]] = None,
        assignee_any: Optional[List[str]] = None,
        completed: Optional[bool] = None,
        is_subtask: Optional[bool] = None,
        sort_by: str = "modified_at",
        sort_ascending: bool = False,
    ) -> Dict[str, Any]:
        """
        Search for tasks.

        Args:
            workspace_gid: Workspace to search
            text: Text to search for
            projects_any: Filter by projects
            assignee_any: Filter by assignees
            completed: Filter by completion status
            is_subtask: Filter subtasks
            sort_by: Sort field
            sort_ascending: Sort direction

        Returns:
            Search results
        """
        params: Dict[str, Any] = {
            "sort_by": sort_by,
            "sort_ascending": str(sort_ascending).lower(),
        }
        if text:
            params["text"] = text
        if projects_any:
            params["projects.any"] = ",".join(projects_any)
        if assignee_any:
            params["assignee.any"] = ",".join(assignee_any)
        if completed is not None:
            params["completed"] = str(completed).lower()
        if is_subtask is not None:
            params["is_subtask"] = str(is_subtask).lower()

        resp = await self.client.get(
            f"/workspaces/{workspace_gid}/tasks/search",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
