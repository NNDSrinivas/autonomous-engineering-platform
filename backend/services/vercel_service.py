"""
Vercel service for NAVI connector integration.

Provides syncing and querying of Vercel projects and deployments.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class VercelService(ConnectorServiceBase):
    """Service for Vercel deployment integration."""

    PROVIDER = "vercel"
    SUPPORTED_ITEM_TYPES = ["project", "deployment"]
    WRITE_OPERATIONS = ["redeploy", "cancel_deployment"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Vercel projects and deployments to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (project, deployment)
            **kwargs: Additional args

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.vercel_client import VercelClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        team_id = config.get("team_id")

        if not access_token:
            raise ValueError("Vercel access token not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with VercelClient(access_token=access_token, team_id=team_id) as client:
            # Sync projects
            if "project" in types_to_sync:
                data = await client.list_projects(limit=50)
                projects = data.get("projects", [])
                counts["project"] = 0

                for proj in projects:
                    proj_id = proj.get("id", "")
                    name = proj.get("name", "Untitled")
                    framework = proj.get("framework", "")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="project",
                        external_id=proj_id,
                        title=name,
                        url=f"https://vercel.com/{proj.get('accountId', '')}/{name}",
                        metadata={
                            "framework": framework,
                            "updated_at": proj.get("updatedAt"),
                        },
                    )
                    counts["project"] += 1

                logger.info(
                    "navi_vercel_sync_projects",
                    user_id=user_id,
                    count=counts["project"],
                )

            # Sync deployments
            if "deployment" in types_to_sync:
                data = await client.list_deployments(limit=50)
                deployments = data.get("deployments", [])
                counts["deployment"] = 0

                for deploy in deployments:
                    deploy_id = deploy.get("uid", "")
                    name = deploy.get("name", "Untitled")
                    state = deploy.get("state", "unknown")
                    url = deploy.get("url", "")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="deployment",
                        external_id=deploy_id,
                        title=name,
                        url=(
                            f"https://{url}"
                            if url and not url.startswith("http")
                            else url
                        ),
                        metadata={
                            "state": state,
                            "target": deploy.get("target"),
                            "created_at": deploy.get("created"),
                        },
                    )
                    counts["deployment"] += 1

                logger.info(
                    "navi_vercel_sync_deployments",
                    user_id=user_id,
                    count=counts["deployment"],
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
        Perform write operations on Vercel.

        Supported operations:
        - redeploy: Redeploy an existing deployment
        - cancel_deployment: Cancel a deployment

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with operation outcome
        """
        from backend.integrations.vercel_client import VercelClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        team_id = config.get("team_id")

        if not access_token:
            raise ValueError("Vercel access token not configured")

        async with VercelClient(access_token=access_token, team_id=team_id) as client:
            if operation == "redeploy":
                deployment_id = kwargs.get("deployment_id")
                target = kwargs.get("target")

                if not deployment_id:
                    raise ValueError("deployment_id is required")

                result = await client.redeploy(
                    deployment_id=deployment_id, target=target
                )

                return {
                    "success": True,
                    "deployment_id": result.get("id"),
                    "url": result.get("url"),
                }

            elif operation == "cancel_deployment":
                deployment_id = kwargs.get("deployment_id")

                if not deployment_id:
                    raise ValueError("deployment_id is required")

                await client.cancel_deployment(deployment_id=deployment_id)
                return {"success": True, "deployment_id": deployment_id}

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_projects(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Vercel projects.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of project dicts
        """
        from backend.integrations.vercel_client import VercelClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        team_id = config.get("team_id")

        if not access_token:
            return []

        async with VercelClient(access_token=access_token, team_id=team_id) as client:
            data = await client.list_projects(limit=max_results)
            projects = data.get("projects", [])

            return [
                {
                    "id": proj.get("id", ""),
                    "name": proj.get("name", "Untitled"),
                    "framework": proj.get("framework", ""),
                    "url": f"https://vercel.com/{proj.get('accountId', '')}/{proj.get('name', '')}",
                }
                for proj in projects
            ]

    @classmethod
    async def list_deployments(
        cls,
        db,
        connection: Dict[str, Any],
        project_id: Optional[str] = None,
        state: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Vercel deployments.

        Args:
            db: Database session
            connection: Connector connection dict
            project_id: Filter by project
            state: Filter by state (BUILDING, ERROR, READY, etc.)
            max_results: Maximum results to return

        Returns:
            List of deployment dicts
        """
        from backend.integrations.vercel_client import VercelClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        team_id = config.get("team_id")

        if not access_token:
            return []

        async with VercelClient(access_token=access_token, team_id=team_id) as client:
            data = await client.list_deployments(
                project_id=project_id,
                state=state,
                limit=max_results,
            )
            deployments = data.get("deployments", [])

            return [
                {
                    "id": d.get("uid", ""),
                    "name": d.get("name", "Untitled"),
                    "state": d.get("state", "unknown"),
                    "target": d.get("target", "preview"),
                    "url": f"https://{d.get('url', '')}" if d.get("url") else "",
                    "created_at": d.get("created", ""),
                }
                for d in deployments
            ]

    @classmethod
    async def get_deployment_status(
        cls,
        db,
        connection: Dict[str, Any],
        deployment_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get status of a Vercel deployment.

        Args:
            db: Database session
            connection: Connector connection dict
            deployment_id: Deployment ID

        Returns:
            Deployment status dict or None
        """
        from backend.integrations.vercel_client import VercelClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        team_id = config.get("team_id")

        if not access_token:
            return None

        async with VercelClient(access_token=access_token, team_id=team_id) as client:
            deployment = await client.get_deployment(deployment_id)

            if not deployment:
                return None

            return {
                "id": deployment.get("id", ""),
                "name": deployment.get("name", "Untitled"),
                "state": deployment.get("readyState", "unknown"),
                "target": deployment.get("target", "preview"),
                "url": (
                    f"https://{deployment.get('url', '')}"
                    if deployment.get("url")
                    else ""
                ),
                "created_at": deployment.get("createdAt", ""),
                "ready_at": deployment.get("ready"),
                "error_message": deployment.get("errorMessage"),
            }
