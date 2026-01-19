"""
Snyk service for NAVI connector integration.

Provides syncing and querying of Snyk vulnerabilities, projects, and security data.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class SnykService(ConnectorServiceBase):
    """Service for Snyk security integration."""

    PROVIDER = "snyk"
    SUPPORTED_ITEM_TYPES = ["vulnerability", "project"]
    WRITE_OPERATIONS = ["ignore_issue"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Snyk vulnerabilities and projects to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (vulnerability, project)
            **kwargs: Additional args (org_id)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.snyk_client import SnykClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        org_id = config.get("org_id") or kwargs.get("org_id")

        if not api_token:
            raise ValueError("Snyk API token not configured")

        if not org_id:
            raise ValueError("Snyk organization ID not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with SnykClient(api_token=api_token) as client:
            # Sync projects
            if "project" in types_to_sync:
                projects_data = await client.list_projects(org_id=org_id, limit=100)
                projects = projects_data.get("projects", [])
                counts["project"] = 0

                for proj in projects:
                    proj_id = proj.get("id", "")
                    name = proj.get("name", "Untitled")
                    origin = proj.get("origin", "")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="project",
                        external_id=proj_id,
                        title=name,
                        url=f"https://app.snyk.io/org/{org_id}/project/{proj_id}",
                        metadata={
                            "origin": origin,
                            "type": proj.get("type"),
                            "target_file": proj.get("targetFile"),
                        },
                    )
                    counts["project"] += 1

                logger.info(
                    "snyk.sync_projects",
                    user_id=user_id,
                    org_id=org_id,
                    count=counts["project"],
                )

            # Sync vulnerabilities for each project
            if "vulnerability" in types_to_sync:
                projects_data = await client.list_projects(org_id=org_id, limit=50)
                projects = projects_data.get("projects", [])
                counts["vulnerability"] = 0

                for proj in projects[:10]:  # Limit to first 10 projects
                    proj_id = proj.get("id", "")
                    try:
                        issues_data = await client.list_issues(org_id=org_id, project_id=proj_id)
                        issues = issues_data.get("issues", [])

                        for issue in issues:
                            issue_id = issue.get("id", "")
                            title = issue.get("title") or issue.get("issueData", {}).get("title", "Unknown")
                            severity = issue.get("severity") or issue.get("issueData", {}).get("severity", "unknown")

                            cls.upsert_item(
                                db=db,
                                user_id=user_id,
                                provider=cls.PROVIDER,
                                item_type="vulnerability",
                                external_id=f"{proj_id}:{issue_id}",
                                title=title,
                                url=f"https://app.snyk.io/org/{org_id}/project/{proj_id}",
                                metadata={
                                    "project_id": proj_id,
                                    "project_name": proj.get("name"),
                                    "severity": severity,
                                    "package_name": issue.get("pkgName"),
                                    "package_version": issue.get("pkgVersions"),
                                },
                            )
                            counts["vulnerability"] += 1
                    except Exception as e:
                        logger.warning(
                            "snyk.sync_issues_failed",
                            project_id=proj_id,
                            error=str(e),
                        )

                logger.info(
                    "snyk.sync_vulnerabilities",
                    user_id=user_id,
                    org_id=org_id,
                    count=counts["vulnerability"],
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
        Perform write operations on Snyk.

        Supported operations:
        - ignore_issue: Ignore a vulnerability

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with updated item info
        """
        from backend.integrations.snyk_client import SnykClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        org_id = config.get("org_id")

        if not api_token:
            raise ValueError("Snyk API token not configured")

        async with SnykClient(api_token=api_token) as client:
            if operation == "ignore_issue":
                project_id = kwargs.get("project_id")
                issue_id = kwargs.get("issue_id")
                reason = kwargs.get("reason", "Not applicable")

                if not project_id or not issue_id:
                    raise ValueError("project_id and issue_id are required")

                await client.ignore_issue(
                    org_id=org_id,
                    project_id=project_id,
                    issue_id=issue_id,
                    reason=reason,
                )

                return {
                    "success": True,
                    "issue_id": issue_id,
                    "status": "ignored",
                }

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_projects(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List Snyk projects.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of project dicts
        """
        from backend.integrations.snyk_client import SnykClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        org_id = config.get("org_id")

        if not api_token or not org_id:
            return []

        async with SnykClient(api_token=api_token) as client:
            data = await client.list_projects(org_id=org_id, limit=max_results)
            projects = data.get("projects", [])

            return [
                {
                    "id": proj.get("id", ""),
                    "name": proj.get("name", "Untitled"),
                    "origin": proj.get("origin", ""),
                    "type": proj.get("type", ""),
                    "target_file": proj.get("targetFile", ""),
                    "url": f"https://app.snyk.io/org/{org_id}/project/{proj.get('id', '')}",
                }
                for proj in projects
            ]

    @classmethod
    async def list_vulnerabilities(
        cls,
        db,
        connection: Dict[str, Any],
        project_id: Optional[str] = None,
        severity: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List Snyk vulnerabilities.

        Args:
            db: Database session
            connection: Connector connection dict
            project_id: Filter by project
            severity: Filter by severity (critical, high, medium, low)
            max_results: Maximum results to return

        Returns:
            List of vulnerability dicts
        """
        from backend.integrations.snyk_client import SnykClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        org_id = config.get("org_id")

        if not api_token or not org_id:
            return []

        results = []

        async with SnykClient(api_token=api_token) as client:
            if project_id:
                # Get issues for specific project
                try:
                    data = await client.list_issues(org_id=org_id, project_id=project_id)
                    issues = data.get("issues", [])

                    for issue in issues:
                        vuln = cls._format_vulnerability(issue, project_id, org_id)
                        if severity and vuln.get("severity", "").lower() != severity.lower():
                            continue
                        results.append(vuln)

                except Exception as e:
                    logger.warning("snyk.list_issues_failed", error=str(e))
            else:
                # Get issues from first few projects
                projects_data = await client.list_projects(org_id=org_id, limit=10)
                projects = projects_data.get("projects", [])

                for proj in projects[:5]:
                    proj_id = proj.get("id", "")
                    try:
                        data = await client.list_issues(org_id=org_id, project_id=proj_id)
                        issues = data.get("issues", [])

                        for issue in issues:
                            vuln = cls._format_vulnerability(issue, proj_id, org_id, proj.get("name"))
                            if severity and vuln.get("severity", "").lower() != severity.lower():
                                continue
                            results.append(vuln)

                    except Exception as e:
                        logger.warning("snyk.list_issues_failed", project_id=proj_id, error=str(e))

        return results[:max_results]

    @classmethod
    def _format_vulnerability(
        cls,
        issue: Dict[str, Any],
        project_id: str,
        org_id: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a Snyk issue into a vulnerability dict."""
        issue_data = issue.get("issueData", {})

        return {
            "id": issue.get("id", ""),
            "title": issue_data.get("title") or issue.get("title", "Unknown"),
            "severity": issue_data.get("severity") or issue.get("severity", "unknown"),
            "package_name": issue.get("pkgName", ""),
            "package_version": str(issue.get("pkgVersions", [""])[0]) if issue.get("pkgVersions") else "",
            "project_id": project_id,
            "project_name": project_name,
            "url": f"https://app.snyk.io/org/{org_id}/project/{project_id}",
            "cvss_score": issue_data.get("cvssScore"),
            "exploit_maturity": issue_data.get("exploitMaturity"),
            "is_patchable": issue.get("isPatchable", False),
            "is_upgradeable": issue.get("isUpgradable", False),
        }

    @classmethod
    async def get_vulnerability_count(
        cls,
        db,
        connection: Dict[str, Any],
    ) -> Dict[str, int]:
        """
        Get vulnerability counts by severity.

        Args:
            db: Database session
            connection: Connector connection dict

        Returns:
            Dict with counts by severity
        """
        from backend.integrations.snyk_client import SnykClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")
        org_id = config.get("org_id")

        if not api_token or not org_id:
            return {}

        async with SnykClient(api_token=api_token) as client:
            try:
                data = await client.get_latest_issue_counts(org_id=org_id)
                results = data.get("results", [])

                counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
                for result in results:
                    severity = result.get("severity", {})
                    counts["critical"] += severity.get("critical", 0)
                    counts["high"] += severity.get("high", 0)
                    counts["medium"] += severity.get("medium", 0)
                    counts["low"] += severity.get("low", 0)

                return counts
            except Exception as e:
                logger.warning("snyk.get_counts_failed", error=str(e))
                return {}
