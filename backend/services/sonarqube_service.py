"""
SonarQube service for NAVI integration.

Provides query operations for SonarQube projects, issues, and quality gates.
"""

from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    SyncResult,
    WriteResult,
)
from backend.integrations.sonarqube_client import SonarQubeClient

logger = structlog.get_logger(__name__)


class SonarQubeService(ConnectorServiceBase):
    """
    SonarQube connector service for NAVI.

    Supports:
    - Projects (list)
    - Issues (list, search)
    - Quality Gates (get status)
    """

    PROVIDER = "sonarqube"
    SUPPORTED_ITEM_TYPES = ["project", "issue"]
    WRITE_OPERATIONS = []  # SonarQube is read-only via API for most operations

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """Sync projects from SonarQube."""
        logger.info("sonarqube_service.sync_items.start", connector_id=connection.get("id"))

        try:
            credentials = cls.get_credentials(connection)
            config = connection.get("config", {})

            if not credentials:
                return SyncResult(success=False, error="No credentials found")

            token = credentials.get("token") or credentials.get("access_token")
            base_url = config.get("base_url") or credentials.get("base_url")

            if not token or not base_url:
                return SyncResult(success=False, error="Missing token or base_url")

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            async with SonarQubeClient(base_url, token) as client:
                projects_data = await client.search_projects(page_size=100)
                projects = projects_data.get("components", [])

                for project in projects:
                    external_id = project.get("key", "")

                    data = {
                        "qualifier": project.get("qualifier"),
                        "visibility": project.get("visibility"),
                        "last_analysis_date": project.get("lastAnalysisDate"),
                    }

                    result = cls.upsert_item(
                        db=db,
                        connector_id=connector_id,
                        item_type="project",
                        external_id=external_id,
                        title=project.get("name"),
                        status="active",
                        url=f"{base_url}/dashboard?id={external_id}",
                        user_id=user_id,
                        org_id=org_id,
                        data=data,
                    )

                    items_synced += 1
                    if result == "created":
                        items_created += 1
                    else:
                        items_updated += 1

            cls.update_sync_status(db=db, connector_id=connector_id, status="success")

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("sonarqube_service.sync_items.error", error=str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        connection: Dict[str, Any],
        action: str,
        data: Dict[str, Any],
    ) -> WriteResult:
        """SonarQube is mostly read-only."""
        return WriteResult(success=False, error="Write operations not supported")

    @classmethod
    async def list_projects(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List SonarQube projects."""
        try:
            credentials = cls.get_credentials(connection)
            config = connection.get("config", {})

            if not credentials:
                return []

            token = credentials.get("token") or credentials.get("access_token")
            base_url = config.get("base_url") or credentials.get("base_url")

            if not token or not base_url:
                return []

            async with SonarQubeClient(base_url, token) as client:
                projects_data = await client.search_projects(page_size=max_results)
                projects = projects_data.get("components", [])

                return [
                    {
                        "key": p.get("key"),
                        "name": p.get("name"),
                        "visibility": p.get("visibility"),
                        "last_analysis": p.get("lastAnalysisDate"),
                        "url": f"{base_url}/dashboard?id={p.get('key')}",
                    }
                    for p in projects[:max_results]
                ]

        except Exception as e:
            logger.error("sonarqube_service.list_projects.error", error=str(e))
            return []

    @classmethod
    async def list_issues(
        cls,
        db: Session,
        connection: Dict[str, Any],
        project_key: Optional[str] = None,
        severity: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List SonarQube issues."""
        try:
            credentials = cls.get_credentials(connection)
            config = connection.get("config", {})

            if not credentials:
                return []

            token = credentials.get("token") or credentials.get("access_token")
            base_url = config.get("base_url") or credentials.get("base_url")

            if not token or not base_url:
                return []

            async with SonarQubeClient(base_url, token) as client:
                issues_data = await client.search_issues(
                    component_keys=[project_key] if project_key else None,
                    severities=[severity] if severity else None,
                    page_size=max_results,
                )
                issues = issues_data.get("issues", [])

                return [
                    {
                        "key": issue.get("key"),
                        "message": issue.get("message"),
                        "severity": issue.get("severity"),
                        "type": issue.get("type"),
                        "component": issue.get("component"),
                        "line": issue.get("line"),
                        "status": issue.get("status"),
                        "effort": issue.get("effort"),
                    }
                    for issue in issues[:max_results]
                ]

        except Exception as e:
            logger.error("sonarqube_service.list_issues.error", error=str(e))
            return []

    @classmethod
    async def get_quality_gate(
        cls,
        db: Session,
        connection: Dict[str, Any],
        project_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get quality gate status for a project."""
        try:
            credentials = cls.get_credentials(connection)
            config = connection.get("config", {})

            if not credentials:
                return None

            token = credentials.get("token") or credentials.get("access_token")
            base_url = config.get("base_url") or credentials.get("base_url")

            if not token or not base_url:
                return None

            async with SonarQubeClient(base_url, token) as client:
                gate_data = await client.get_quality_gate_status(project_key)

                return {
                    "status": gate_data.get("projectStatus", {}).get("status"),
                    "conditions": gate_data.get("projectStatus", {}).get("conditions", []),
                }

        except Exception as e:
            logger.error("sonarqube_service.get_quality_gate.error", error=str(e))
            return None
