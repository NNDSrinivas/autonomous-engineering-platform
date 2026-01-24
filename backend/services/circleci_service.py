"""
CircleCI service for NAVI connector integration.

Provides syncing and querying of CircleCI pipelines, workflows, and jobs.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class CircleCIService(ConnectorServiceBase):
    """Service for CircleCI CI/CD integration."""

    PROVIDER = "circleci"
    SUPPORTED_ITEM_TYPES = ["pipeline", "workflow", "job"]
    WRITE_OPERATIONS = ["trigger_pipeline", "rerun_workflow", "cancel_workflow"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync CircleCI pipelines to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (pipeline, workflow)
            **kwargs: Additional args (project_slug required)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.circleci_client import CircleCIClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        project_slug = kwargs.get("project_slug") or config.get("project_slug")

        if not api_token:
            raise ValueError("CircleCI API token not configured")

        if not project_slug:
            raise ValueError("CircleCI project_slug is required")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with CircleCIClient(api_token=api_token) as client:
            # Sync pipelines
            if "pipeline" in types_to_sync:
                data = await client.list_project_pipelines(project_slug)
                pipelines = data.get("items", [])
                counts["pipeline"] = 0

                for pipeline in pipelines:
                    pipeline_id = pipeline.get("id", "")
                    pipeline_num = pipeline.get("number", "")
                    state = pipeline.get("state", "unknown")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="pipeline",
                        external_id=pipeline_id,
                        title=f"Pipeline #{pipeline_num}",
                        url=f"https://app.circleci.com/pipelines/{project_slug}/{pipeline_num}",
                        metadata={
                            "project_slug": project_slug,
                            "number": pipeline_num,
                            "state": state,
                            "trigger": pipeline.get("trigger", {}).get("type"),
                            "created_at": pipeline.get("created_at"),
                        },
                    )
                    counts["pipeline"] += 1

                logger.info(
                    "circleci.sync_pipelines",
                    user_id=user_id,
                    project_slug=project_slug,
                    count=counts["pipeline"],
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
        Perform write operations on CircleCI.

        Supported operations:
        - trigger_pipeline: Trigger a new pipeline
        - rerun_workflow: Re-run a workflow
        - cancel_workflow: Cancel a workflow

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with operation outcome
        """
        from backend.integrations.circleci_client import CircleCIClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            raise ValueError("CircleCI API token not configured")

        async with CircleCIClient(api_token=api_token) as client:
            if operation == "trigger_pipeline":
                project_slug = kwargs.get("project_slug")
                branch = kwargs.get("branch", "main")
                parameters = kwargs.get("parameters")

                if not project_slug:
                    raise ValueError("project_slug is required")

                result = await client.trigger_pipeline(
                    project_slug=project_slug,
                    branch=branch,
                    parameters=parameters,
                )

                return {
                    "success": True,
                    "pipeline_id": result.get("id"),
                    "number": result.get("number"),
                }

            elif operation == "rerun_workflow":
                workflow_id = kwargs.get("workflow_id")
                from_failed = kwargs.get("from_failed", False)

                if not workflow_id:
                    raise ValueError("workflow_id is required")

                result = await client.rerun_workflow(
                    workflow_id=workflow_id,
                    from_failed=from_failed,
                )

                return {"success": True, "workflow_id": result.get("workflow_id")}

            elif operation == "cancel_workflow":
                workflow_id = kwargs.get("workflow_id")

                if not workflow_id:
                    raise ValueError("workflow_id is required")

                await client.cancel_workflow(workflow_id=workflow_id)
                return {"success": True, "workflow_id": workflow_id}

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_pipelines(
        cls,
        db,
        connection: Dict[str, Any],
        project_slug: str,
        branch: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List CircleCI pipelines for a project.

        Args:
            db: Database session
            connection: Connector connection dict
            project_slug: CircleCI project slug
            branch: Filter by branch
            max_results: Maximum results to return

        Returns:
            List of pipeline dicts
        """
        from backend.integrations.circleci_client import CircleCIClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with CircleCIClient(api_token=api_token) as client:
            data = await client.list_project_pipelines(project_slug, branch=branch)
            pipelines = data.get("items", [])[:max_results]

            return [
                {
                    "id": p.get("id", ""),
                    "number": p.get("number"),
                    "state": p.get("state", "unknown"),
                    "trigger_type": p.get("trigger", {}).get("type", ""),
                    "created_at": p.get("created_at", ""),
                    "url": f"https://app.circleci.com/pipelines/{project_slug}/{p.get('number', '')}",
                }
                for p in pipelines
            ]

    @classmethod
    async def get_pipeline_status(
        cls,
        db,
        connection: Dict[str, Any],
        pipeline_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get status of a CircleCI pipeline with its workflows.

        Args:
            db: Database session
            connection: Connector connection dict
            pipeline_id: Pipeline ID

        Returns:
            Pipeline status dict or None
        """
        from backend.integrations.circleci_client import CircleCIClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return None

        async with CircleCIClient(api_token=api_token) as client:
            pipeline = await client.get_pipeline(pipeline_id)

            if not pipeline:
                return None

            # Get workflows for this pipeline
            workflows_data = await client.list_pipeline_workflows(pipeline_id)
            workflows = workflows_data.get("items", [])

            return {
                "id": pipeline.get("id", ""),
                "number": pipeline.get("number"),
                "state": pipeline.get("state", "unknown"),
                "trigger_type": pipeline.get("trigger", {}).get("type", ""),
                "created_at": pipeline.get("created_at", ""),
                "workflows": [
                    {
                        "id": wf.get("id", ""),
                        "name": wf.get("name", ""),
                        "status": wf.get("status", "unknown"),
                    }
                    for wf in workflows
                ],
            }

    @classmethod
    async def get_job_status(
        cls,
        db,
        connection: Dict[str, Any],
        project_slug: str,
        job_number: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get status of a CircleCI job.

        Args:
            db: Database session
            connection: Connector connection dict
            project_slug: CircleCI project slug
            job_number: Job number

        Returns:
            Job status dict or None
        """
        from backend.integrations.circleci_client import CircleCIClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return None

        async with CircleCIClient(api_token=api_token) as client:
            job = await client.get_job_details(project_slug, job_number)

            if not job:
                return None

            return {
                "name": job.get("name", ""),
                "job_number": job.get("job_number"),
                "status": job.get("status", "unknown"),
                "started_at": job.get("started_at", ""),
                "stopped_at": job.get("stopped_at", ""),
                "duration": job.get("duration"),
            }
