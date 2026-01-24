"""
Figma service for NAVI connector integration.

Provides syncing and querying of Figma files, projects, and comments.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class FigmaService(ConnectorServiceBase):
    """Service for Figma design integration."""

    PROVIDER = "figma"
    SUPPORTED_ITEM_TYPES = ["file", "project", "comment"]
    WRITE_OPERATIONS = ["post_comment"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Figma files and projects to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (file, project)
            **kwargs: Additional args (team_id, project_id)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.figma_client import FigmaClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            raise ValueError("Figma access token not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with FigmaClient(access_token=access_token) as client:
            team_id = kwargs.get("team_id")
            project_id = kwargs.get("project_id")

            # Sync projects if team_id provided
            if "project" in types_to_sync and team_id:
                projects_data = await client.get_team_projects(team_id)
                projects = projects_data.get("projects", [])
                counts["project"] = 0

                for proj in projects:
                    proj_id = proj.get("id", "")
                    name = proj.get("name", "Untitled")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="project",
                        external_id=str(proj_id),
                        title=name,
                        url=f"https://www.figma.com/files/project/{proj_id}",
                        metadata={"team_id": team_id},
                    )
                    counts["project"] += 1

                logger.info(
                    "figma.sync_projects",
                    user_id=user_id,
                    team_id=team_id,
                    count=counts["project"],
                )

            # Sync files if project_id provided
            if "file" in types_to_sync and project_id:
                files_data = await client.get_project_files(project_id)
                files = files_data.get("files", [])
                counts["file"] = 0

                for f in files:
                    file_key = f.get("key", "")
                    name = f.get("name", "Untitled")
                    thumbnail = f.get("thumbnail_url", "")
                    last_modified = f.get("last_modified", "")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="file",
                        external_id=file_key,
                        title=name,
                        url=f"https://www.figma.com/file/{file_key}",
                        metadata={
                            "project_id": project_id,
                            "thumbnail_url": thumbnail,
                            "last_modified": last_modified,
                        },
                    )
                    counts["file"] += 1

                logger.info(
                    "figma.sync_files",
                    user_id=user_id,
                    project_id=project_id,
                    count=counts["file"],
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
        Perform write operations on Figma.

        Supported operations:
        - post_comment: Add a comment to a file

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with created/updated item info
        """
        from backend.integrations.figma_client import FigmaClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            raise ValueError("Figma access token not configured")

        async with FigmaClient(access_token=access_token) as client:
            if operation == "post_comment":
                file_key = kwargs.get("file_key")
                message = kwargs.get("message")

                if not file_key or not message:
                    raise ValueError(
                        "file_key and message are required for post_comment"
                    )

                result = await client.post_comment(
                    file_key=file_key,
                    message=message,
                    client_meta=kwargs.get("client_meta"),
                    comment_id=kwargs.get("reply_to"),
                )

                return {
                    "success": True,
                    "comment_id": result.get("id"),
                    "message": message,
                }

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_files(
        cls,
        db,
        connection: Dict[str, Any],
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List files in a Figma project.

        Args:
            db: Database session
            connection: Connector connection dict
            project_id: Figma project ID

        Returns:
            List of file dicts
        """
        from backend.integrations.figma_client import FigmaClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return []

        async with FigmaClient(access_token=access_token) as client:
            data = await client.get_project_files(project_id)
            files = data.get("files", [])

            return [
                {
                    "key": f.get("key", ""),
                    "name": f.get("name", "Untitled"),
                    "thumbnail_url": f.get("thumbnail_url", ""),
                    "last_modified": f.get("last_modified", ""),
                    "url": f"https://www.figma.com/file/{f.get('key', '')}",
                }
                for f in files
            ]

    @classmethod
    async def get_file(
        cls,
        db,
        connection: Dict[str, Any],
        file_key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get details of a Figma file.

        Args:
            db: Database session
            connection: Connector connection dict
            file_key: Figma file key

        Returns:
            File dict or None
        """
        from backend.integrations.figma_client import FigmaClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return None

        async with FigmaClient(access_token=access_token) as client:
            data = await client.get_file(file_key, depth=1)

            return {
                "key": file_key,
                "name": data.get("name", "Untitled"),
                "last_modified": data.get("lastModified", ""),
                "version": data.get("version", ""),
                "thumbnail_url": data.get("thumbnailUrl", ""),
                "url": f"https://www.figma.com/file/{file_key}",
                "pages": [
                    {"id": page.get("id"), "name": page.get("name")}
                    for page in data.get("document", {}).get("children", [])
                ],
            }

    @classmethod
    async def get_comments(
        cls,
        db,
        connection: Dict[str, Any],
        file_key: str,
    ) -> List[Dict[str, Any]]:
        """
        Get comments on a Figma file.

        Args:
            db: Database session
            connection: Connector connection dict
            file_key: Figma file key

        Returns:
            List of comment dicts
        """
        from backend.integrations.figma_client import FigmaClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return []

        async with FigmaClient(access_token=access_token) as client:
            data = await client.get_comments(file_key)
            comments = data.get("comments", [])

            return [
                {
                    "id": c.get("id", ""),
                    "message": c.get("message", ""),
                    "user": c.get("user", {}).get("handle", "Unknown"),
                    "created_at": c.get("created_at", ""),
                    "resolved_at": c.get("resolved_at"),
                }
                for c in comments
            ]

    @classmethod
    async def list_team_projects(
        cls,
        db,
        connection: Dict[str, Any],
        team_id: str,
    ) -> List[Dict[str, Any]]:
        """
        List projects in a Figma team.

        Args:
            db: Database session
            connection: Connector connection dict
            team_id: Figma team ID

        Returns:
            List of project dicts
        """
        from backend.integrations.figma_client import FigmaClient

        config = connection.get("config", {})
        access_token = config.get("access_token")

        if not access_token:
            return []

        async with FigmaClient(access_token=access_token) as client:
            data = await client.get_team_projects(team_id)
            projects = data.get("projects", [])

            return [
                {
                    "id": p.get("id", ""),
                    "name": p.get("name", "Untitled"),
                    "url": f"https://www.figma.com/files/project/{p.get('id', '')}",
                }
                for p in projects
            ]
