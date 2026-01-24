"""
Snyk API client for security vulnerability management.

Provides access to Snyk organizations, projects, issues, and tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class SnykClient:
    """
    Async Snyk API client.

    Supports:
    - Organization management
    - Project management
    - Issue (vulnerability) tracking
    - Security testing
    - Dependencies
    """

    BASE_URL = "https://api.snyk.io/v1"

    def __init__(
        self,
        api_token: str,
        timeout: float = 30.0,
    ):
        self.api_token = api_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "SnykClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"token {self.api_token}",
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
        resp = await self.client.get("/user/me")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Organizations
    # -------------------------------------------------------------------------

    async def list_orgs(self) -> List[Dict[str, Any]]:
        """List organizations the user has access to."""
        resp = await self.client.get("/orgs")
        resp.raise_for_status()
        return resp.json().get("orgs", [])

    async def get_org(
        self,
        org_id: str,
    ) -> Dict[str, Any]:
        """Get organization details."""
        resp = await self.client.get(f"/org/{org_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_org_members(
        self,
        org_id: str,
    ) -> List[Dict[str, Any]]:
        """Get organization members."""
        resp = await self.client.get(f"/org/{org_id}/members")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def list_projects(
        self,
        org_id: str,
        limit: int = 100,
        offset: int = 0,
        target_file: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List projects in an organization.

        Args:
            org_id: Organization ID
            limit: Results per page
            offset: Pagination offset
            target_file: Filter by target file
            origin: Filter by origin (github, gitlab, etc.)

        Returns:
            List of projects with pagination
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if target_file:
            params["targetFile"] = target_file
        if origin:
            params["origin"] = origin

        resp = await self.client.get(f"/org/{org_id}/projects", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_project(
        self,
        org_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Get project details."""
        resp = await self.client.get(f"/org/{org_id}/project/{project_id}")
        resp.raise_for_status()
        return resp.json()

    async def activate_project(
        self,
        org_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Activate a project."""
        resp = await self.client.post(f"/org/{org_id}/project/{project_id}/activate")
        resp.raise_for_status()
        return resp.json()

    async def deactivate_project(
        self,
        org_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Deactivate a project."""
        resp = await self.client.post(f"/org/{org_id}/project/{project_id}/deactivate")
        resp.raise_for_status()
        return resp.json()

    async def delete_project(
        self,
        org_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Delete a project."""
        resp = await self.client.delete(f"/org/{org_id}/project/{project_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Issues (Vulnerabilities)
    # -------------------------------------------------------------------------

    async def list_issues(
        self,
        org_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Get aggregated issues for a project."""
        resp = await self.client.post(
            f"/org/{org_id}/project/{project_id}/aggregated-issues",
        )
        resp.raise_for_status()
        return resp.json()

    async def get_issue_paths(
        self,
        org_id: str,
        project_id: str,
        issue_id: str,
    ) -> Dict[str, Any]:
        """Get issue paths."""
        resp = await self.client.get(
            f"/org/{org_id}/project/{project_id}/issue/{issue_id}/paths",
        )
        resp.raise_for_status()
        return resp.json()

    async def ignore_issue(
        self,
        org_id: str,
        project_id: str,
        issue_id: str,
        reason: str,
        reason_type: str = "not-vulnerable",
        expires: Optional[str] = None,
        ignore_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ignore an issue.

        Args:
            org_id: Organization ID
            project_id: Project ID
            issue_id: Issue ID
            reason: Reason for ignoring
            reason_type: not-vulnerable, wont-fix, temporary-ignore
            expires: Expiration date (ISO 8601)
            ignore_path: Specific path to ignore

        Returns:
            Ignore result
        """
        payload: Dict[str, Any] = {
            "reason": reason,
            "reasonType": reason_type,
        }
        if expires:
            payload["expires"] = expires
        if ignore_path:
            payload["ignorePath"] = ignore_path

        resp = await self.client.post(
            f"/org/{org_id}/project/{project_id}/ignore/{issue_id}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Dependencies
    # -------------------------------------------------------------------------

    async def list_dependencies(
        self,
        org_id: str,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "dependency",
        order: str = "asc",
    ) -> Dict[str, Any]:
        """List dependencies for an organization."""
        params = {
            "page": page,
            "perPage": per_page,
            "sortBy": sort_by,
            "order": order,
        }
        resp = await self.client.post(f"/org/{org_id}/dependencies", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_project_dependencies(
        self,
        org_id: str,
        project_id: str,
    ) -> Dict[str, Any]:
        """Get dependencies for a project."""
        resp = await self.client.get(f"/org/{org_id}/project/{project_id}/dep-graph")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Testing
    # -------------------------------------------------------------------------

    async def test_maven(
        self,
        org_id: str,
        group_id: str,
        artifact_id: str,
        version: str,
    ) -> Dict[str, Any]:
        """Test a Maven package for vulnerabilities."""
        resp = await self.client.get(
            f"/test/maven/{group_id}/{artifact_id}/{version}",
            params={"org": org_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def test_npm(
        self,
        org_id: str,
        package_name: str,
        version: str,
    ) -> Dict[str, Any]:
        """Test an npm package for vulnerabilities."""
        resp = await self.client.get(
            f"/test/npm/{package_name}/{version}",
            params={"org": org_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def test_pip(
        self,
        org_id: str,
        package_name: str,
        version: str,
    ) -> Dict[str, Any]:
        """Test a pip package for vulnerabilities."""
        resp = await self.client.get(
            f"/test/pip/{package_name}/{version}",
            params={"org": org_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def test_rubygems(
        self,
        org_id: str,
        gem_name: str,
        version: str,
    ) -> Dict[str, Any]:
        """Test a RubyGems package for vulnerabilities."""
        resp = await self.client.get(
            f"/test/rubygems/{gem_name}/{version}",
            params={"org": org_id},
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    async def get_latest_issue_counts(
        self,
        org_id: str,
    ) -> Dict[str, Any]:
        """Get latest issue counts for an organization."""
        resp = await self.client.get(f"/reporting/counts/issues/latest?org={org_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_issue_count_history(
        self,
        org_id: str,
        from_date: str,
        to_date: str,
    ) -> Dict[str, Any]:
        """Get issue count history."""
        params = {
            "org": org_id,
            "from": from_date,
            "to": to_date,
        }
        resp = await self.client.get("/reporting/counts/issues", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Integrations
    # -------------------------------------------------------------------------

    async def list_integrations(
        self,
        org_id: str,
    ) -> Dict[str, Any]:
        """List integrations for an organization."""
        resp = await self.client.get(f"/org/{org_id}/integrations")
        resp.raise_for_status()
        return resp.json()

    async def get_integration(
        self,
        org_id: str,
        integration_id: str,
    ) -> Dict[str, Any]:
        """Get integration details."""
        resp = await self.client.get(f"/org/{org_id}/integrations/{integration_id}")
        resp.raise_for_status()
        return resp.json()

    async def import_projects(
        self,
        org_id: str,
        integration_id: str,
        files: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Import projects from an integration.

        Args:
            org_id: Organization ID
            integration_id: Integration ID
            files: List of files to import
                   [{"path": "package.json"}, ...]

        Returns:
            Import result
        """
        payload = {"files": files}
        resp = await self.client.post(
            f"/org/{org_id}/integrations/{integration_id}/import",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        org_id: str,
    ) -> Dict[str, Any]:
        """List webhooks for an organization."""
        resp = await self.client.get(f"/org/{org_id}/webhooks")
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        org_id: str,
        url: str,
        secret: str,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            org_id: Organization ID
            url: Webhook URL
            secret: Webhook secret for verification

        Returns:
            Created webhook
        """
        payload = {
            "url": url,
            "secret": secret,
        }
        resp = await self.client.post(f"/org/{org_id}/webhooks", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(
        self,
        org_id: str,
        webhook_id: str,
    ) -> bool:
        """Delete a webhook."""
        resp = await self.client.delete(f"/org/{org_id}/webhooks/{webhook_id}")
        return resp.status_code == 200
