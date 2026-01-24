"""
GitHub Actions API client for workflow management.

Provides access to GitHub Actions workflows, runs, jobs, and artifacts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class GitHubActionsClient:
    """
    Async GitHub Actions API client.

    Supports:
    - Workflow management
    - Workflow runs and jobs
    - Artifacts
    - Action secrets
    - Environment management
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GitHubActionsClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
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
    # Workflows
    # -------------------------------------------------------------------------

    async def list_workflows(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """List repository workflows."""
        params = {"per_page": per_page, "page": page}
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/workflows",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
    ) -> Dict[str, Any]:
        """Get a specific workflow."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}",
        )
        resp.raise_for_status()
        return resp.json()

    async def dispatch_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Manually trigger a workflow.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_id: Workflow ID or file name
            ref: Git reference (branch/tag)
            inputs: Workflow inputs

        Returns:
            True if dispatch was successful
        """
        payload: Dict[str, Any] = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs

        resp = await self.client.post(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            json=payload,
        )
        return resp.status_code == 204

    async def enable_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
    ) -> bool:
        """Enable a workflow."""
        resp = await self.client.put(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/enable",
        )
        return resp.status_code == 204

    async def disable_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
    ) -> bool:
        """Disable a workflow."""
        resp = await self.client.put(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/disable",
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Workflow Runs
    # -------------------------------------------------------------------------

    async def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
        actor: Optional[str] = None,
        branch: Optional[str] = None,
        event: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        List workflow runs.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_id: Filter by workflow
            actor: Filter by actor
            branch: Filter by branch
            event: Filter by event type
            status: Filter by status (queued, in_progress, completed, etc.)
            per_page: Results per page
            page: Page number

        Returns:
            Workflow runs
        """
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if actor:
            params["actor"] = actor
        if branch:
            params["branch"] = branch
        if event:
            params["event"] = event
        if status:
            params["status"] = status

        if workflow_id:
            url = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            url = f"/repos/{owner}/{repo}/actions/runs"

        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_workflow_run(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> Dict[str, Any]:
        """Get a specific workflow run."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}",
        )
        resp.raise_for_status()
        return resp.json()

    async def rerun_workflow(
        self,
        owner: str,
        repo: str,
        run_id: int,
        enable_debug_logging: bool = False,
    ) -> bool:
        """Re-run a workflow."""
        payload = {}
        if enable_debug_logging:
            payload["enable_debug_logging"] = True

        resp = await self.client.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun",
            json=payload if payload else None,
        )
        return resp.status_code == 201

    async def rerun_failed_jobs(
        self,
        owner: str,
        repo: str,
        run_id: int,
        enable_debug_logging: bool = False,
    ) -> bool:
        """Re-run only failed jobs in a workflow."""
        payload = {}
        if enable_debug_logging:
            payload["enable_debug_logging"] = True

        resp = await self.client.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs",
            json=payload if payload else None,
        )
        return resp.status_code == 201

    async def cancel_workflow_run(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> bool:
        """Cancel a workflow run."""
        resp = await self.client.post(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel",
        )
        return resp.status_code == 202

    async def delete_workflow_run(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> bool:
        """Delete a workflow run."""
        resp = await self.client.delete(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}",
        )
        return resp.status_code == 204

    async def get_workflow_run_logs(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> bytes:
        """Download workflow run logs as a zip file."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content

    # -------------------------------------------------------------------------
    # Jobs
    # -------------------------------------------------------------------------

    async def list_jobs_for_run(
        self,
        owner: str,
        repo: str,
        run_id: int,
        filter: str = "latest",
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        List jobs for a workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            filter: Filter by attempt (latest, all)
            per_page: Results per page
            page: Page number

        Returns:
            Jobs list
        """
        params = {"filter": filter, "per_page": per_page, "page": page}
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_job(
        self,
        owner: str,
        repo: str,
        job_id: int,
    ) -> Dict[str, Any]:
        """Get a specific job."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/jobs/{job_id}",
        )
        resp.raise_for_status()
        return resp.json()

    async def get_job_logs(
        self,
        owner: str,
        repo: str,
        job_id: int,
    ) -> str:
        """Download job logs."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs",
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text

    # -------------------------------------------------------------------------
    # Artifacts
    # -------------------------------------------------------------------------

    async def list_artifacts(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List artifacts for a repository."""
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if name:
            params["name"] = name

        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/artifacts",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_run_artifacts(
        self,
        owner: str,
        repo: str,
        run_id: int,
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """List artifacts for a workflow run."""
        params = {"per_page": per_page, "page": page}
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_artifact(
        self,
        owner: str,
        repo: str,
        artifact_id: int,
    ) -> Dict[str, Any]:
        """Get a specific artifact."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/artifacts/{artifact_id}",
        )
        resp.raise_for_status()
        return resp.json()

    async def download_artifact(
        self,
        owner: str,
        repo: str,
        artifact_id: int,
        archive_format: str = "zip",
    ) -> bytes:
        """Download an artifact."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/{archive_format}",
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content

    async def delete_artifact(
        self,
        owner: str,
        repo: str,
        artifact_id: int,
    ) -> bool:
        """Delete an artifact."""
        resp = await self.client.delete(
            f"/repos/{owner}/{repo}/actions/artifacts/{artifact_id}",
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Secrets
    # -------------------------------------------------------------------------

    async def list_repo_secrets(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """List repository secrets (names only, not values)."""
        params = {"per_page": per_page, "page": page}
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/secrets",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_repo_public_key(
        self,
        owner: str,
        repo: str,
    ) -> Dict[str, Any]:
        """Get the public key for encrypting secrets."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/secrets/public-key",
        )
        resp.raise_for_status()
        return resp.json()

    async def create_or_update_secret(
        self,
        owner: str,
        repo: str,
        secret_name: str,
        encrypted_value: str,
        key_id: str,
    ) -> bool:
        """
        Create or update a repository secret.

        Note: Value must be encrypted using the repository's public key.
        """
        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_id,
        }
        resp = await self.client.put(
            f"/repos/{owner}/{repo}/actions/secrets/{secret_name}",
            json=payload,
        )
        return resp.status_code in (201, 204)

    async def delete_secret(
        self,
        owner: str,
        repo: str,
        secret_name: str,
    ) -> bool:
        """Delete a repository secret."""
        resp = await self.client.delete(
            f"/repos/{owner}/{repo}/actions/secrets/{secret_name}",
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Variables
    # -------------------------------------------------------------------------

    async def list_repo_variables(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """List repository variables."""
        params = {"per_page": per_page, "page": page}
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/variables",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_variable(
        self,
        owner: str,
        repo: str,
        name: str,
    ) -> Dict[str, Any]:
        """Get a repository variable."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/variables/{name}",
        )
        resp.raise_for_status()
        return resp.json()

    async def create_variable(
        self,
        owner: str,
        repo: str,
        name: str,
        value: str,
    ) -> bool:
        """Create a repository variable."""
        payload = {"name": name, "value": value}
        resp = await self.client.post(
            f"/repos/{owner}/{repo}/actions/variables",
            json=payload,
        )
        return resp.status_code == 201

    async def update_variable(
        self,
        owner: str,
        repo: str,
        name: str,
        value: str,
    ) -> bool:
        """Update a repository variable."""
        payload = {"name": name, "value": value}
        resp = await self.client.patch(
            f"/repos/{owner}/{repo}/actions/variables/{name}",
            json=payload,
        )
        return resp.status_code == 204

    async def delete_variable(
        self,
        owner: str,
        repo: str,
        name: str,
    ) -> bool:
        """Delete a repository variable."""
        resp = await self.client.delete(
            f"/repos/{owner}/{repo}/actions/variables/{name}",
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Runners
    # -------------------------------------------------------------------------

    async def list_repo_runners(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
    ) -> Dict[str, Any]:
        """List self-hosted runners for a repository."""
        params = {"per_page": per_page, "page": page}
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/runners",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_runner(
        self,
        owner: str,
        repo: str,
        runner_id: int,
    ) -> Dict[str, Any]:
        """Get a specific runner."""
        resp = await self.client.get(
            f"/repos/{owner}/{repo}/actions/runners/{runner_id}",
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def get_workflow_status_summary(
        self,
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a summary of workflow run statuses."""
        runs = await self.list_workflow_runs(
            owner,
            repo,
            workflow_id=workflow_id,
            per_page=100,
        )

        status_counts: Dict[str, int] = {}
        conclusion_counts: Dict[str, int] = {}

        for run in runs.get("workflow_runs", []):
            status = run.get("status", "unknown")
            conclusion = run.get("conclusion") or "pending"

            status_counts[status] = status_counts.get(status, 0) + 1
            conclusion_counts[conclusion] = conclusion_counts.get(conclusion, 0) + 1

        return {
            "total_runs": runs.get("total_count", 0),
            "status_breakdown": status_counts,
            "conclusion_breakdown": conclusion_counts,
        }

    def format_run_summary(self, run: Dict[str, Any]) -> str:
        """Format a workflow run for display."""
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion") or "pending"
        name = run.get("name", "Unknown")
        run_number = run.get("run_number", 0)
        actor = run.get("actor", {}).get("login", "unknown")
        branch = run.get("head_branch", "unknown")

        return f"#{run_number} {name} [{status}/{conclusion}] by {actor} on {branch}"
