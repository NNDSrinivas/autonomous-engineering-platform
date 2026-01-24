"""
Vercel API client for deployment and project management.

Provides access to Vercel projects, deployments, domains, and logs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class VercelClient:
    """
    Async Vercel API client.

    Supports:
    - Project management
    - Deployment management
    - Domain configuration
    - Environment variables
    - Logs and analytics
    """

    BASE_URL = "https://api.vercel.com"

    def __init__(
        self,
        access_token: str,
        team_id: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.team_id = team_id
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "VercelClient":
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

    def _add_team_param(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add team ID to params if configured."""
        if self.team_id:
            params["teamId"] = self.team_id
        return params

    # -------------------------------------------------------------------------
    # User
    # -------------------------------------------------------------------------

    async def get_user(self) -> Dict[str, Any]:
        """Get the authenticated user."""
        resp = await self.client.get("/v2/user")
        resp.raise_for_status()
        return resp.json()

    async def list_teams(self) -> Dict[str, Any]:
        """List teams the user belongs to."""
        resp = await self.client.get("/v2/teams")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def list_projects(
        self,
        limit: int = 20,
        from_param: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List projects.

        Args:
            limit: Number of projects to return
            from_param: Cursor for pagination
            search: Search query

        Returns:
            List of projects
        """
        params: Dict[str, Any] = {"limit": limit}
        if from_param:
            params["from"] = from_param
        if search:
            params["search"] = search
        params = self._add_team_param(params)

        resp = await self.client.get("/v9/projects", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_project(
        self,
        project_id_or_name: str,
    ) -> Dict[str, Any]:
        """Get a specific project."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v9/projects/{project_id_or_name}", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def create_project(
        self,
        name: str,
        git_repository: Optional[Dict[str, Any]] = None,
        framework: Optional[str] = None,
        public_source: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name
            git_repository: Git repository configuration
            framework: Framework preset (nextjs, gatsby, etc.)
            public_source: Make source code public

        Returns:
            Created project
        """
        payload: Dict[str, Any] = {
            "name": name,
            "publicSource": public_source,
        }
        if git_repository:
            payload["gitRepository"] = git_repository
        if framework:
            payload["framework"] = framework

        params = self._add_team_param({})
        resp = await self.client.post("/v9/projects", json=payload, params=params)
        resp.raise_for_status()
        return resp.json()

    async def delete_project(
        self,
        project_id_or_name: str,
    ) -> bool:
        """Delete a project."""
        params = self._add_team_param({})
        resp = await self.client.delete(
            f"/v9/projects/{project_id_or_name}",
            params=params,
        )
        return resp.status_code == 204

    async def update_project(
        self,
        project_id_or_name: str,
        name: Optional[str] = None,
        build_command: Optional[str] = None,
        dev_command: Optional[str] = None,
        install_command: Optional[str] = None,
        output_directory: Optional[str] = None,
        root_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update project settings."""
        payload: Dict[str, Any] = {}
        if name:
            payload["name"] = name
        if build_command:
            payload["buildCommand"] = build_command
        if dev_command:
            payload["devCommand"] = dev_command
        if install_command:
            payload["installCommand"] = install_command
        if output_directory:
            payload["outputDirectory"] = output_directory
        if root_directory:
            payload["rootDirectory"] = root_directory

        params = self._add_team_param({})
        resp = await self.client.patch(
            f"/v9/projects/{project_id_or_name}",
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Environment Variables
    # -------------------------------------------------------------------------

    async def list_env_vars(
        self,
        project_id_or_name: str,
    ) -> Dict[str, Any]:
        """List environment variables for a project."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v9/projects/{project_id_or_name}/env",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def create_env_var(
        self,
        project_id_or_name: str,
        key: str,
        value: str,
        target: List[str] = None,
        env_type: str = "encrypted",
    ) -> Dict[str, Any]:
        """
        Create an environment variable.

        Args:
            project_id_or_name: Project identifier
            key: Variable name
            value: Variable value
            target: Deployment targets (production, preview, development)
            env_type: Type (encrypted, plain, sensitive)

        Returns:
            Created environment variable
        """
        if target is None:
            target = ["production", "preview", "development"]

        payload = {
            "key": key,
            "value": value,
            "target": target,
            "type": env_type,
        }
        params = self._add_team_param({})
        resp = await self.client.post(
            f"/v10/projects/{project_id_or_name}/env",
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_env_var(
        self,
        project_id_or_name: str,
        env_id: str,
    ) -> bool:
        """Delete an environment variable."""
        params = self._add_team_param({})
        resp = await self.client.delete(
            f"/v9/projects/{project_id_or_name}/env/{env_id}",
            params=params,
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Deployments
    # -------------------------------------------------------------------------

    async def list_deployments(
        self,
        project_id: Optional[str] = None,
        limit: int = 20,
        from_param: Optional[str] = None,
        state: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List deployments.

        Args:
            project_id: Filter by project
            limit: Number of deployments to return
            from_param: Cursor for pagination
            state: Filter by state (BUILDING, ERROR, INITIALIZING, QUEUED, READY, CANCELED)
            target: Filter by target (production, preview)

        Returns:
            List of deployments
        """
        params: Dict[str, Any] = {"limit": limit}
        if project_id:
            params["projectId"] = project_id
        if from_param:
            params["from"] = from_param
        if state:
            params["state"] = state
        if target:
            params["target"] = target
        params = self._add_team_param(params)

        resp = await self.client.get("/v6/deployments", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_deployment(
        self,
        deployment_id_or_url: str,
    ) -> Dict[str, Any]:
        """Get a specific deployment."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v13/deployments/{deployment_id_or_url}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def create_deployment(
        self,
        name: str,
        files: List[Dict[str, Any]],
        project: Optional[str] = None,
        target: str = "production",
        git_source: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new deployment.

        Args:
            name: Deployment name
            files: List of files to deploy
            project: Project ID or name
            target: Deployment target (production, preview)
            git_source: Git source configuration

        Returns:
            Created deployment
        """
        payload: Dict[str, Any] = {
            "name": name,
            "files": files,
            "target": target,
        }
        if project:
            payload["project"] = project
        if git_source:
            payload["gitSource"] = git_source

        params = self._add_team_param({})
        resp = await self.client.post("/v13/deployments", json=payload, params=params)
        resp.raise_for_status()
        return resp.json()

    async def cancel_deployment(
        self,
        deployment_id: str,
    ) -> Dict[str, Any]:
        """Cancel a deployment."""
        params = self._add_team_param({})
        resp = await self.client.patch(
            f"/v12/deployments/{deployment_id}/cancel",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_deployment(
        self,
        deployment_id: str,
    ) -> bool:
        """Delete a deployment."""
        params = self._add_team_param({})
        resp = await self.client.delete(
            f"/v13/deployments/{deployment_id}",
            params=params,
        )
        return resp.status_code == 204

    async def get_deployment_events(
        self,
        deployment_id: str,
    ) -> Dict[str, Any]:
        """Get deployment build logs/events."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v2/deployments/{deployment_id}/events",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def redeploy(
        self,
        deployment_id: str,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Redeploy an existing deployment."""
        payload: Dict[str, Any] = {}
        if target:
            payload["target"] = target

        params = self._add_team_param({})
        resp = await self.client.post(
            f"/v13/deployments/{deployment_id}/redeploy",
            json=payload if payload else None,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Domains
    # -------------------------------------------------------------------------

    async def list_domains(
        self,
        limit: int = 20,
        from_param: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List domains."""
        params: Dict[str, Any] = {"limit": limit}
        if from_param:
            params["from"] = from_param
        params = self._add_team_param(params)

        resp = await self.client.get("/v5/domains", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_domain(
        self,
        domain: str,
    ) -> Dict[str, Any]:
        """Get a specific domain."""
        params = self._add_team_param({})
        resp = await self.client.get(f"/v5/domains/{domain}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def add_domain(
        self,
        name: str,
    ) -> Dict[str, Any]:
        """Add a domain."""
        payload = {"name": name}
        params = self._add_team_param({})
        resp = await self.client.post("/v5/domains", json=payload, params=params)
        resp.raise_for_status()
        return resp.json()

    async def remove_domain(
        self,
        domain: str,
    ) -> bool:
        """Remove a domain."""
        params = self._add_team_param({})
        resp = await self.client.delete(f"/v6/domains/{domain}", params=params)
        return resp.status_code == 200

    async def list_project_domains(
        self,
        project_id_or_name: str,
    ) -> Dict[str, Any]:
        """List domains for a project."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v9/projects/{project_id_or_name}/domains",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def add_project_domain(
        self,
        project_id_or_name: str,
        domain: str,
        redirect: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a domain to a project."""
        payload: Dict[str, Any] = {"name": domain}
        if redirect:
            payload["redirect"] = redirect

        params = self._add_team_param({})
        resp = await self.client.post(
            f"/v10/projects/{project_id_or_name}/domains",
            json=payload,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def remove_project_domain(
        self,
        project_id_or_name: str,
        domain: str,
    ) -> bool:
        """Remove a domain from a project."""
        params = self._add_team_param({})
        resp = await self.client.delete(
            f"/v9/projects/{project_id_or_name}/domains/{domain}",
            params=params,
        )
        return resp.status_code == 200

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """List webhooks for a project."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v1/webhooks?projectId={project_id}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        project_ids: List[str],
        url: str,
        events: List[str],
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            project_ids: List of project IDs
            url: Webhook URL
            events: Events to subscribe to (deployment.created, deployment.succeeded, etc.)

        Returns:
            Created webhook
        """
        payload = {
            "projectIds": project_ids,
            "url": url,
            "events": events,
        }
        params = self._add_team_param({})
        resp = await self.client.post("/v1/webhooks", json=payload, params=params)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(
        self,
        webhook_id: str,
    ) -> bool:
        """Delete a webhook."""
        params = self._add_team_param({})
        resp = await self.client.delete(f"/v1/webhooks/{webhook_id}", params=params)
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Logs
    # -------------------------------------------------------------------------

    async def get_deployment_logs(
        self,
        deployment_id: str,
        direction: str = "backward",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get runtime logs for a deployment."""
        params: Dict[str, Any] = {
            "direction": direction,
            "limit": limit,
        }
        params = self._add_team_param(params)

        resp = await self.client.get(
            f"/v2/deployments/{deployment_id}/logs",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Checks
    # -------------------------------------------------------------------------

    async def list_deployment_checks(
        self,
        deployment_id: str,
    ) -> Dict[str, Any]:
        """List checks for a deployment."""
        params = self._add_team_param({})
        resp = await self.client.get(
            f"/v1/deployments/{deployment_id}/checks",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def get_deployment_url(
        self,
        deployment: Dict[str, Any],
    ) -> str:
        """Get the URL for a deployment."""
        url = deployment.get("url")
        if url and not url.startswith("http"):
            return f"https://{url}"
        return url or ""

    def format_deployment_status(
        self,
        deployment: Dict[str, Any],
    ) -> str:
        """Format deployment status for display."""
        state = deployment.get("state", "UNKNOWN")
        name = deployment.get("name", "unknown")
        target = deployment.get("target", "preview")
        url = self.get_deployment_url(deployment)

        return f"{name} [{target}] - {state}\n{url}"
