"""
CircleCI API client for CI/CD pipeline management.

Provides access to CircleCI projects, pipelines, workflows, and jobs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class CircleCIClient:
    """
    Async CircleCI API v2 client.

    Supports:
    - Project management
    - Pipeline triggering and monitoring
    - Workflow management
    - Job logs and artifacts
    - Insights and metrics
    """

    BASE_URL = "https://circleci.com/api/v2"

    def __init__(
        self,
        api_token: str,
        timeout: float = 30.0,
    ):
        self.api_token = api_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "CircleCIClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Circle-Token": self.api_token,
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

    async def get_me(self) -> Dict[str, Any]:
        """Get the authenticated user."""
        resp = await self.client.get("/me")
        resp.raise_for_status()
        return resp.json()

    async def get_collaborations(self) -> Dict[str, Any]:
        """Get organizations the user collaborates with."""
        resp = await self.client.get("/me/collaborations")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def get_project(
        self,
        project_slug: str,
    ) -> Dict[str, Any]:
        """
        Get a project.

        Args:
            project_slug: Project slug (e.g., gh/owner/repo or bb/owner/repo)

        Returns:
            Project details
        """
        resp = await self.client.get(f"/project/{project_slug}")
        resp.raise_for_status()
        return resp.json()

    async def list_project_pipelines(
        self,
        project_slug: str,
        branch: Optional[str] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List pipelines for a project."""
        params: Dict[str, Any] = {}
        if branch:
            params["branch"] = branch
        if page_token:
            params["page-token"] = page_token

        resp = await self.client.get(
            f"/project/{project_slug}/pipeline",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_checkout_keys(
        self,
        project_slug: str,
    ) -> Dict[str, Any]:
        """Get checkout keys for a project."""
        resp = await self.client.get(f"/project/{project_slug}/checkout-key")
        resp.raise_for_status()
        return resp.json()

    async def list_environment_variables(
        self,
        project_slug: str,
    ) -> Dict[str, Any]:
        """List environment variables for a project."""
        resp = await self.client.get(f"/project/{project_slug}/envvar")
        resp.raise_for_status()
        return resp.json()

    async def create_environment_variable(
        self,
        project_slug: str,
        name: str,
        value: str,
    ) -> Dict[str, Any]:
        """Create an environment variable."""
        payload = {"name": name, "value": value}
        resp = await self.client.post(
            f"/project/{project_slug}/envvar",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_environment_variable(
        self,
        project_slug: str,
        name: str,
    ) -> Dict[str, Any]:
        """Delete an environment variable."""
        resp = await self.client.delete(f"/project/{project_slug}/envvar/{name}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Pipelines
    # -------------------------------------------------------------------------

    async def get_pipeline(
        self,
        pipeline_id: str,
    ) -> Dict[str, Any]:
        """Get a specific pipeline."""
        resp = await self.client.get(f"/pipeline/{pipeline_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_pipeline_config(
        self,
        pipeline_id: str,
    ) -> Dict[str, Any]:
        """Get the configuration for a pipeline."""
        resp = await self.client.get(f"/pipeline/{pipeline_id}/config")
        resp.raise_for_status()
        return resp.json()

    async def trigger_pipeline(
        self,
        project_slug: str,
        branch: Optional[str] = None,
        tag: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a new pipeline.

        Args:
            project_slug: Project slug
            branch: Git branch to run on
            tag: Git tag to run on
            parameters: Pipeline parameters

        Returns:
            Created pipeline
        """
        payload: Dict[str, Any] = {}
        if branch:
            payload["branch"] = branch
        if tag:
            payload["tag"] = tag
        if parameters:
            payload["parameters"] = parameters

        resp = await self.client.post(
            f"/project/{project_slug}/pipeline",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_pipeline_workflows(
        self,
        pipeline_id: str,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List workflows for a pipeline."""
        params = {}
        if page_token:
            params["page-token"] = page_token

        resp = await self.client.get(
            f"/pipeline/{pipeline_id}/workflow",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Workflows
    # -------------------------------------------------------------------------

    async def get_workflow(
        self,
        workflow_id: str,
    ) -> Dict[str, Any]:
        """Get a specific workflow."""
        resp = await self.client.get(f"/workflow/{workflow_id}")
        resp.raise_for_status()
        return resp.json()

    async def approve_workflow_job(
        self,
        workflow_id: str,
        approval_request_id: str,
    ) -> Dict[str, Any]:
        """Approve a pending approval job."""
        resp = await self.client.post(
            f"/workflow/{workflow_id}/approve/{approval_request_id}",
        )
        resp.raise_for_status()
        return resp.json()

    async def cancel_workflow(
        self,
        workflow_id: str,
    ) -> Dict[str, Any]:
        """Cancel a running workflow."""
        resp = await self.client.post(f"/workflow/{workflow_id}/cancel")
        resp.raise_for_status()
        return resp.json()

    async def rerun_workflow(
        self,
        workflow_id: str,
        from_failed: bool = False,
        sparse_tree: bool = False,
    ) -> Dict[str, Any]:
        """
        Rerun a workflow.

        Args:
            workflow_id: Workflow ID
            from_failed: Only rerun from failed jobs
            sparse_tree: Use sparse tree for rerun

        Returns:
            Rerun result
        """
        payload: Dict[str, Any] = {}
        if from_failed:
            payload["from_failed"] = True
        if sparse_tree:
            payload["sparse_tree"] = True

        resp = await self.client.post(
            f"/workflow/{workflow_id}/rerun",
            json=payload if payload else None,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_workflow_jobs(
        self,
        workflow_id: str,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List jobs for a workflow."""
        params = {}
        if page_token:
            params["page-token"] = page_token

        resp = await self.client.get(f"/workflow/{workflow_id}/job", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Jobs
    # -------------------------------------------------------------------------

    async def get_job_details(
        self,
        project_slug: str,
        job_number: int,
    ) -> Dict[str, Any]:
        """Get details for a specific job."""
        resp = await self.client.get(f"/project/{project_slug}/job/{job_number}")
        resp.raise_for_status()
        return resp.json()

    async def cancel_job(
        self,
        project_slug: str,
        job_number: int,
    ) -> Dict[str, Any]:
        """Cancel a running job."""
        resp = await self.client.post(f"/project/{project_slug}/job/{job_number}/cancel")
        resp.raise_for_status()
        return resp.json()

    async def get_job_artifacts(
        self,
        project_slug: str,
        job_number: int,
    ) -> Dict[str, Any]:
        """Get artifacts for a job."""
        resp = await self.client.get(f"/project/{project_slug}/{job_number}/artifacts")
        resp.raise_for_status()
        return resp.json()

    async def get_job_tests(
        self,
        project_slug: str,
        job_number: int,
    ) -> Dict[str, Any]:
        """Get test results for a job."""
        resp = await self.client.get(f"/project/{project_slug}/{job_number}/tests")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Insights
    # -------------------------------------------------------------------------

    async def get_project_summary(
        self,
        project_slug: str,
        reporting_window: str = "last-90-days",
        branches: Optional[List[str]] = None,
        workflow_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get summary metrics for a project.

        Args:
            project_slug: Project slug
            reporting_window: Time window (last-7-days, last-30-days, last-90-days)
            branches: Filter by branches
            workflow_names: Filter by workflow names

        Returns:
            Project metrics summary
        """
        params: Dict[str, Any] = {"reporting-window": reporting_window}
        if branches:
            params["branches"] = ",".join(branches)
        if workflow_names:
            params["workflow-names"] = ",".join(workflow_names)

        resp = await self.client.get(
            f"/insights/{project_slug}/summary",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_workflow_metrics(
        self,
        project_slug: str,
        workflow_name: str,
        reporting_window: str = "last-90-days",
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get metrics for a specific workflow."""
        params: Dict[str, Any] = {"reporting-window": reporting_window}
        if branch:
            params["branch"] = branch

        resp = await self.client.get(
            f"/insights/{project_slug}/workflows/{workflow_name}",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_job_timeseries(
        self,
        project_slug: str,
        workflow_name: str,
        granularity: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get job timeseries data."""
        params: Dict[str, Any] = {"granularity": granularity}
        if start_date:
            params["start-date"] = start_date
        if end_date:
            params["end-date"] = end_date

        resp = await self.client.get(
            f"/insights/{project_slug}/workflows/{workflow_name}/jobs",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_flaky_tests(
        self,
        project_slug: str,
    ) -> Dict[str, Any]:
        """Get flaky tests for a project."""
        resp = await self.client.get(f"/insights/{project_slug}/flaky-tests")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Contexts
    # -------------------------------------------------------------------------

    async def list_contexts(
        self,
        owner_slug: str,
        owner_type: str = "organization",
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List contexts.

        Args:
            owner_slug: Organization or account slug
            owner_type: account or organization
            page_token: Pagination token

        Returns:
            List of contexts
        """
        params: Dict[str, Any] = {
            "owner-slug": owner_slug,
            "owner-type": owner_type,
        }
        if page_token:
            params["page-token"] = page_token

        resp = await self.client.get("/context", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_context(
        self,
        name: str,
        owner_slug: str,
        owner_type: str = "organization",
    ) -> Dict[str, Any]:
        """Create a new context."""
        payload = {
            "name": name,
            "owner": {
                "slug": owner_slug,
                "type": owner_type,
            },
        }
        resp = await self.client.post("/context", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_context(
        self,
        context_id: str,
    ) -> Dict[str, Any]:
        """Get a specific context."""
        resp = await self.client.get(f"/context/{context_id}")
        resp.raise_for_status()
        return resp.json()

    async def delete_context(
        self,
        context_id: str,
    ) -> Dict[str, Any]:
        """Delete a context."""
        resp = await self.client.delete(f"/context/{context_id}")
        resp.raise_for_status()
        return resp.json()

    async def list_context_variables(
        self,
        context_id: str,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List environment variables in a context."""
        params = {}
        if page_token:
            params["page-token"] = page_token

        resp = await self.client.get(
            f"/context/{context_id}/environment-variable",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def add_context_variable(
        self,
        context_id: str,
        name: str,
        value: str,
    ) -> Dict[str, Any]:
        """Add or update an environment variable in a context."""
        payload = {"value": value}
        resp = await self.client.put(
            f"/context/{context_id}/environment-variable/{name}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_context_variable(
        self,
        context_id: str,
        name: str,
    ) -> Dict[str, Any]:
        """Delete an environment variable from a context."""
        resp = await self.client.delete(
            f"/context/{context_id}/environment-variable/{name}",
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        project_slug: str,
    ) -> Dict[str, Any]:
        """List webhooks for a project."""
        resp = await self.client.get(f"/webhook?scope-type=project&scope-id={project_slug}")
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        project_slug: str,
        name: str,
        url: str,
        events: List[str],
        signing_secret: str,
        verify_tls: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            project_slug: Project slug
            name: Webhook name
            url: Webhook URL
            events: Events to subscribe to (workflow-completed, job-completed)
            signing_secret: Secret for signature verification
            verify_tls: Verify TLS certificates

        Returns:
            Created webhook
        """
        payload = {
            "name": name,
            "events": events,
            "url": url,
            "verify-tls": verify_tls,
            "signing-secret": signing_secret,
            "scope": {
                "type": "project",
                "id": project_slug,
            },
        }
        resp = await self.client.post("/webhook", json=payload)
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

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def make_project_slug(
        self,
        vcs_type: str,
        org: str,
        repo: str,
    ) -> str:
        """
        Create a project slug.

        Args:
            vcs_type: Version control type (gh, bb, github, bitbucket)
            org: Organization or owner name
            repo: Repository name

        Returns:
            Project slug (e.g., gh/owner/repo)
        """
        vcs_map = {
            "github": "gh",
            "bitbucket": "bb",
        }
        vcs = vcs_map.get(vcs_type.lower(), vcs_type.lower())
        return f"{vcs}/{org}/{repo}"
