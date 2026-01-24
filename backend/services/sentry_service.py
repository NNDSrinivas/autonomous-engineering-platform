"""
Sentry service for NAVI connector integration.

Provides syncing and querying of Sentry issues, projects, and releases.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class SentryService(ConnectorServiceBase):
    """Service for Sentry error tracking integration."""

    PROVIDER = "sentry"
    SUPPORTED_ITEM_TYPES = ["issue", "project", "release"]
    WRITE_OPERATIONS = ["resolve_issue", "ignore_issue"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Sentry issues and projects to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (issue, project, release)
            **kwargs: Additional args (org_slug, project_slug)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.sentry_client import SentryClient

        config = connection.get("config", {})
        auth_token = config.get("access_token") or config.get("auth_token")
        org_slug = config.get("organization_slug") or kwargs.get("org_slug")

        if not auth_token:
            raise ValueError("Sentry auth token not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with SentryClient(
            auth_token=auth_token,
            organization_slug=org_slug,
        ) as client:
            # Sync projects
            if "project" in types_to_sync and org_slug:
                projects = await client.list_projects(org_slug=org_slug)
                counts["project"] = 0

                for proj in projects:
                    proj_slug = proj.get("slug", "")
                    name = proj.get("name", "Untitled")
                    platform = proj.get("platform", "")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="project",
                        external_id=proj_slug,
                        title=name,
                        url=f"https://sentry.io/organizations/{org_slug}/projects/{proj_slug}/",
                        metadata={
                            "platform": platform,
                            "status": proj.get("status"),
                        },
                    )
                    counts["project"] += 1

                logger.info(
                    "sentry.sync_projects",
                    user_id=user_id,
                    org_slug=org_slug,
                    count=counts["project"],
                )

            # Sync issues
            if "issue" in types_to_sync and org_slug:
                issues_data = await client.list_issues(
                    org_slug=org_slug, statsPeriod="24h"
                )
                issues = issues_data.get("issues", [])
                counts["issue"] = 0

                for issue in issues:
                    issue_id = str(issue.get("id", ""))
                    title = issue.get("title", "Unknown Error")
                    culprit = issue.get("culprit", "")
                    project_info = issue.get("project", {})

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="issue",
                        external_id=issue_id,
                        title=title,
                        content=culprit,
                        url=issue.get("permalink", ""),
                        metadata={
                            "project": project_info.get("slug"),
                            "status": issue.get("status"),
                            "level": issue.get("level"),
                            "count": issue.get("count"),
                            "user_count": issue.get("userCount"),
                            "first_seen": issue.get("firstSeen"),
                            "last_seen": issue.get("lastSeen"),
                        },
                    )
                    counts["issue"] += 1

                logger.info(
                    "sentry.sync_issues",
                    user_id=user_id,
                    org_slug=org_slug,
                    count=counts["issue"],
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
        Perform write operations on Sentry.

        Supported operations:
        - resolve_issue: Mark an issue as resolved
        - ignore_issue: Ignore an issue

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with updated item info
        """
        from backend.integrations.sentry_client import SentryClient

        config = connection.get("config", {})
        auth_token = config.get("access_token") or config.get("auth_token")
        org_slug = config.get("organization_slug")

        if not auth_token:
            raise ValueError("Sentry auth token not configured")

        async with SentryClient(
            auth_token=auth_token,
            organization_slug=org_slug,
        ) as client:
            if operation == "resolve_issue":
                issue_id = kwargs.get("issue_id")
                if not issue_id:
                    raise ValueError("issue_id is required for resolve_issue")

                await client.update_issue(issue_id, status="resolved")
                return {
                    "success": True,
                    "issue_id": issue_id,
                    "status": "resolved",
                }

            elif operation == "ignore_issue":
                issue_id = kwargs.get("issue_id")
                if not issue_id:
                    raise ValueError("issue_id is required for ignore_issue")

                await client.update_issue(issue_id, status="ignored")
                return {
                    "success": True,
                    "issue_id": issue_id,
                    "status": "ignored",
                }

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_issues(
        cls,
        db,
        connection: Dict[str, Any],
        project_slug: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Sentry issues.

        Args:
            db: Database session
            connection: Connector connection dict
            project_slug: Filter by project
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of issue dicts
        """
        from backend.integrations.sentry_client import SentryClient

        config = connection.get("config", {})
        auth_token = config.get("access_token") or config.get("auth_token")
        org_slug = config.get("organization_slug")

        if not auth_token:
            return []

        async with SentryClient(
            auth_token=auth_token,
            organization_slug=org_slug,
        ) as client:
            data = await client.list_issues(
                project_slug=project_slug,
                query=query,
                statsPeriod="24h",
            )
            issues = data.get("issues", [])[:max_results]

            return [
                {
                    "id": str(issue.get("id", "")),
                    "title": issue.get("title", "Unknown Error"),
                    "culprit": issue.get("culprit", ""),
                    "level": issue.get("level", "error"),
                    "status": issue.get("status", "unresolved"),
                    "count": issue.get("count", 0),
                    "user_count": issue.get("userCount", 0),
                    "project": issue.get("project", {}).get("slug", ""),
                    "url": issue.get("permalink", ""),
                    "first_seen": issue.get("firstSeen", ""),
                    "last_seen": issue.get("lastSeen", ""),
                }
                for issue in issues
            ]

    @classmethod
    async def get_issue_details(
        cls,
        db,
        connection: Dict[str, Any],
        issue_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a Sentry issue.

        Args:
            db: Database session
            connection: Connector connection dict
            issue_id: Sentry issue ID

        Returns:
            Issue dict with details or None
        """
        from backend.integrations.sentry_client import SentryClient

        config = connection.get("config", {})
        auth_token = config.get("access_token") or config.get("auth_token")
        org_slug = config.get("organization_slug")

        if not auth_token:
            return None

        async with SentryClient(
            auth_token=auth_token,
            organization_slug=org_slug,
        ) as client:
            issue = await client.get_issue(issue_id)

            if not issue:
                return None

            return {
                "id": str(issue.get("id", "")),
                "title": issue.get("title", "Unknown Error"),
                "culprit": issue.get("culprit", ""),
                "level": issue.get("level", "error"),
                "status": issue.get("status", "unresolved"),
                "count": issue.get("count", 0),
                "user_count": issue.get("userCount", 0),
                "project": issue.get("project", {}).get("slug", ""),
                "url": issue.get("permalink", ""),
                "first_seen": issue.get("firstSeen", ""),
                "last_seen": issue.get("lastSeen", ""),
                "metadata": issue.get("metadata", {}),
                "type": issue.get("type", "error"),
                "assignedTo": issue.get("assignedTo"),
            }

    @classmethod
    async def list_projects(
        cls,
        db,
        connection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        List Sentry projects.

        Args:
            db: Database session
            connection: Connector connection dict

        Returns:
            List of project dicts
        """
        from backend.integrations.sentry_client import SentryClient

        config = connection.get("config", {})
        auth_token = config.get("access_token") or config.get("auth_token")
        org_slug = config.get("organization_slug")

        if not auth_token:
            return []

        async with SentryClient(
            auth_token=auth_token,
            organization_slug=org_slug,
        ) as client:
            projects = await client.list_projects(org_slug=org_slug)

            return [
                {
                    "slug": proj.get("slug", ""),
                    "name": proj.get("name", "Untitled"),
                    "platform": proj.get("platform", ""),
                    "status": proj.get("status", ""),
                    "url": f"https://sentry.io/organizations/{org_slug}/projects/{proj.get('slug', '')}/",
                }
                for proj in projects
            ]
