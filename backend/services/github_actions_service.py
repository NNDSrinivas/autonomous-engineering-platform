"""
GitHub Actions service for NAVI connector integration.

Provides syncing and querying of GitHub Actions workflows, runs, and jobs.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class GitHubActionsService(ConnectorServiceBase):
    """Service for GitHub Actions CI/CD integration."""

    PROVIDER = "github_actions"
    SUPPORTED_ITEM_TYPES = ["workflow", "workflow_run", "job"]
    WRITE_OPERATIONS = ["trigger_workflow", "rerun_workflow", "cancel_run"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync GitHub Actions workflows and runs to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (workflow, workflow_run)
            **kwargs: Additional args (owner, repo required)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.github_actions_client import GitHubActionsClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        owner = kwargs.get("owner") or config.get("owner")
        repo = kwargs.get("repo") or config.get("repo")

        if not access_token:
            raise ValueError("GitHub access token not configured")

        if not owner or not repo:
            raise ValueError("GitHub owner and repo are required")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with GitHubActionsClient(access_token=access_token) as client:
            # Sync workflows
            if "workflow" in types_to_sync:
                data = await client.list_workflows(owner, repo)
                workflows = data.get("workflows", [])
                counts["workflow"] = 0

                for wf in workflows:
                    wf_id = str(wf.get("id", ""))
                    name = wf.get("name", "Untitled")
                    state = wf.get("state", "unknown")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="workflow",
                        external_id=wf_id,
                        title=name,
                        url=wf.get("html_url", ""),
                        metadata={
                            "owner": owner,
                            "repo": repo,
                            "state": state,
                            "path": wf.get("path"),
                        },
                    )
                    counts["workflow"] += 1

                logger.info(
                    "github_actions.sync_workflows",
                    user_id=user_id,
                    repo=f"{owner}/{repo}",
                    count=counts["workflow"],
                )

            # Sync workflow runs
            if "workflow_run" in types_to_sync:
                data = await client.list_workflow_runs(owner, repo, per_page=50)
                runs = data.get("workflow_runs", [])
                counts["workflow_run"] = 0

                for run in runs:
                    run_id = str(run.get("id", ""))
                    name = run.get("name", "Untitled")
                    status = run.get("status", "unknown")
                    conclusion = run.get("conclusion") or "pending"

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="workflow_run",
                        external_id=run_id,
                        title=f"{name} #{run.get('run_number', '')}",
                        url=run.get("html_url", ""),
                        metadata={
                            "owner": owner,
                            "repo": repo,
                            "status": status,
                            "conclusion": conclusion,
                            "run_number": run.get("run_number"),
                            "workflow_id": run.get("workflow_id"),
                            "branch": run.get("head_branch"),
                            "event": run.get("event"),
                            "actor": run.get("actor", {}).get("login"),
                        },
                    )
                    counts["workflow_run"] += 1

                logger.info(
                    "github_actions.sync_runs",
                    user_id=user_id,
                    repo=f"{owner}/{repo}",
                    count=counts["workflow_run"],
                )

        return counts

    @classmethod
    async def write_item(
        cls,
        db,
        connection: Dict[str, Any],
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform write operations on GitHub Actions.

        Supported operations:
        - trigger_workflow: Manually trigger a workflow
        - rerun_workflow: Re-run a workflow
        - cancel_run: Cancel a running workflow

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with operation outcome
        """
        from backend.integrations.github_actions_client import GitHubActionsClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            raise ValueError("GitHub access token not configured")

        async with GitHubActionsClient(access_token=access_token) as client:
            if operation == "trigger_workflow":
                owner = kwargs.get("owner")
                repo = kwargs.get("repo")
                workflow_id = kwargs.get("workflow_id")
                ref = kwargs.get("ref", "main")
                inputs = kwargs.get("inputs")

                if not owner or not repo or not workflow_id:
                    raise ValueError("owner, repo, and workflow_id are required")

                success = await client.dispatch_workflow(
                    owner=owner,
                    repo=repo,
                    workflow_id=workflow_id,
                    ref=ref,
                    inputs=inputs,
                )

                return {
                    "success": success,
                    "workflow_id": workflow_id,
                    "ref": ref,
                }

            elif operation == "rerun_workflow":
                owner = kwargs.get("owner")
                repo = kwargs.get("repo")
                run_id = kwargs.get("run_id")

                if not owner or not repo or not run_id:
                    raise ValueError("owner, repo, and run_id are required")

                success = await client.rerun_workflow(
                    owner=owner,
                    repo=repo,
                    run_id=int(run_id),
                )

                return {"success": success, "run_id": run_id}

            elif operation == "cancel_run":
                owner = kwargs.get("owner")
                repo = kwargs.get("repo")
                run_id = kwargs.get("run_id")

                if not owner or not repo or not run_id:
                    raise ValueError("owner, repo, and run_id are required")

                success = await client.cancel_workflow_run(
                    owner=owner,
                    repo=repo,
                    run_id=int(run_id),
                )

                return {"success": success, "run_id": run_id}

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_workflows(
        cls,
        db,
        connection: Dict[str, Any],
        owner: str,
        repo: str,
    ) -> List[Dict[str, Any]]:
        """
        List workflows for a repository.

        Args:
            db: Database session
            connection: Connector connection dict
            owner: Repository owner
            repo: Repository name

        Returns:
            List of workflow dicts
        """
        from backend.integrations.github_actions_client import GitHubActionsClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return []

        async with GitHubActionsClient(access_token=access_token) as client:
            data = await client.list_workflows(owner, repo)
            workflows = data.get("workflows", [])

            return [
                {
                    "id": str(wf.get("id", "")),
                    "name": wf.get("name", "Untitled"),
                    "path": wf.get("path", ""),
                    "state": wf.get("state", "unknown"),
                    "url": wf.get("html_url", ""),
                }
                for wf in workflows
            ]

    @classmethod
    async def list_workflow_runs(
        cls,
        db,
        connection: Dict[str, Any],
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List workflow runs for a repository.

        Args:
            db: Database session
            connection: Connector connection dict
            owner: Repository owner
            repo: Repository name
            workflow_id: Filter by workflow
            status: Filter by status
            max_results: Maximum results to return

        Returns:
            List of workflow run dicts
        """
        from backend.integrations.github_actions_client import GitHubActionsClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return []

        async with GitHubActionsClient(access_token=access_token) as client:
            data = await client.list_workflow_runs(
                owner=owner,
                repo=repo,
                workflow_id=workflow_id,
                status=status,
                per_page=max_results,
            )
            runs = data.get("workflow_runs", [])

            return [
                {
                    "id": str(run.get("id", "")),
                    "name": run.get("name", "Untitled"),
                    "run_number": run.get("run_number"),
                    "status": run.get("status", "unknown"),
                    "conclusion": run.get("conclusion") or "pending",
                    "branch": run.get("head_branch", ""),
                    "event": run.get("event", ""),
                    "actor": run.get("actor", {}).get("login", ""),
                    "url": run.get("html_url", ""),
                    "created_at": run.get("created_at", ""),
                    "updated_at": run.get("updated_at", ""),
                }
                for run in runs
            ]

    @classmethod
    async def get_run_status(
        cls,
        db,
        connection: Dict[str, Any],
        owner: str,
        repo: str,
        run_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get status of a workflow run.

        Args:
            db: Database session
            connection: Connector connection dict
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            Run status dict or None
        """
        from backend.integrations.github_actions_client import GitHubActionsClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return None

        async with GitHubActionsClient(access_token=access_token) as client:
            run = await client.get_workflow_run(owner, repo, run_id)

            if not run:
                return None

            return {
                "id": str(run.get("id", "")),
                "name": run.get("name", "Untitled"),
                "run_number": run.get("run_number"),
                "status": run.get("status", "unknown"),
                "conclusion": run.get("conclusion") or "pending",
                "branch": run.get("head_branch", ""),
                "event": run.get("event", ""),
                "actor": run.get("actor", {}).get("login", ""),
                "url": run.get("html_url", ""),
                "created_at": run.get("created_at", ""),
                "updated_at": run.get("updated_at", ""),
            }
