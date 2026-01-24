"""
Linear service for NAVI integration.

Provides sync, query, and write operations for Linear issues, projects, and cycles.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    ConnectorItem,
    SyncResult,
    WriteResult,
)
from backend.integrations.linear_client import LinearClient

logger = structlog.get_logger(__name__)


class LinearService(ConnectorServiceBase):
    """
    Linear connector service for NAVI.

    Supports:
    - Issues (list, search, create, update, comment)
    - Projects (list)
    - Cycles/Sprints (list)
    """

    PROVIDER = "linear"
    SUPPORTED_ITEM_TYPES = ["issue", "project", "cycle"]
    WRITE_OPERATIONS = ["create_issue", "update_issue", "add_comment", "update_status"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync issues and projects from Linear to database.

        Args:
            db: Database session
            connection: Connection with credentials
            item_types: Optional list of types to sync (default: all)

        Returns:
            SyncResult with sync statistics
        """
        logger.info(
            "linear_service.sync_items.start",
            connector_id=connection.get("id"),
            item_types=item_types,
        )

        try:
            # Get credentials
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for Linear connection"
                )

            access_token = credentials.get("access_token")
            if not access_token:
                return SyncResult(
                    success=False, error="No access token in Linear credentials"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            types_to_sync = item_types or ["issue", "project"]

            async with LinearClient(access_token) as client:
                # Get current user for assignee matching
                viewer = await client.get_viewer()
                viewer.get("email", "")
                viewer.get("name", "")

                if "issue" in types_to_sync:
                    # Fetch issues
                    issues_data = await client.list_issues(first=100)
                    issues = issues_data.get("nodes", [])

                    for issue in issues:
                        external_id = issue.get("id")
                        identifier = issue.get("identifier", "")

                        # Determine assignee
                        assignee = None
                        if issue.get("assignee"):
                            assignee = issue["assignee"].get("name") or issue[
                                "assignee"
                            ].get("email")

                        # Build data dict with full issue details
                        data = {
                            "identifier": identifier,
                            "priority": issue.get("priority"),
                            "priorityLabel": issue.get("priorityLabel"),
                            "estimate": issue.get("estimate"),
                            "team": issue.get("team"),
                            "project": issue.get("project"),
                            "cycle": issue.get("cycle"),
                            "labels": [
                                label
                                for label in issue.get("labels", {}).get("nodes", [])
                            ],
                            "creator": issue.get("creator"),
                            "assignee": issue.get("assignee"),
                        }

                        # Parse dates
                        created_at = None
                        updated_at = None
                        if issue.get("createdAt"):
                            try:
                                created_at = datetime.fromisoformat(
                                    issue["createdAt"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass
                        if issue.get("updatedAt"):
                            try:
                                updated_at = datetime.fromisoformat(
                                    issue["updatedAt"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass

                        # Upsert to database
                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="issue",
                            external_id=external_id,
                            title=issue.get("title"),
                            description=issue.get("description"),
                            status=issue.get("state", {}).get("name"),
                            url=issue.get("url"),
                            assignee=assignee,
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                            external_created_at=created_at,
                            external_updated_at=updated_at,
                        )

                        if result:
                            items_synced += 1
                            items_created += (
                                1  # Simplified - could track actual creates vs updates
                            )

                    logger.info(
                        "linear_service.sync_items.issues_synced",
                        count=len(issues),
                    )

                if "project" in types_to_sync:
                    # Fetch projects
                    projects = await client.list_projects(first=50)

                    for project in projects:
                        external_id = project.get("id")

                        # Build data dict
                        data = {
                            "state": project.get("state"),
                            "progress": project.get("progress"),
                            "startDate": project.get("startDate"),
                            "targetDate": project.get("targetDate"),
                            "teams": project.get("teams", {}).get("nodes", []),
                            "lead": project.get("lead"),
                        }

                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="project",
                            external_id=external_id,
                            title=project.get("name"),
                            description=project.get("description"),
                            status=project.get("state"),
                            url=project.get("url"),
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                        )

                        if result:
                            items_synced += 1

                    logger.info(
                        "linear_service.sync_items.projects_synced",
                        count=len(projects),
                    )

            # Update connector sync status
            cls.update_sync_status(db, connector_id, "success")

            logger.info(
                "linear_service.sync_items.complete",
                items_synced=items_synced,
                items_created=items_created,
            )

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("linear_service.sync_items.error", error=str(e))
            cls.update_sync_status(db, connection.get("id"), "error", str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        user_id: str,
        item_type: str,
        action: str,
        data: Dict[str, Any],
        org_id: Optional[str] = None,
    ) -> WriteResult:
        """
        Write operation to Linear (create issue, update, comment).

        Args:
            db: Database session
            user_id: User performing the action
            item_type: Type of item (currently only "issue" supported)
            action: Action to perform (create_issue, update_issue, add_comment, update_status)
            data: Data for the operation
            org_id: Optional organization ID

        Returns:
            WriteResult with success status and created item details
        """
        logger.info(
            "linear_service.write_item.start",
            user_id=user_id,
            item_type=item_type,
            action=action,
        )

        try:
            # Get connection
            connection = cls.get_connection(db, user_id, org_id)
            if not connection:
                return WriteResult(
                    success=False, error="No Linear connection found for user"
                )

            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(success=False, error="No credentials found")

            access_token = credentials.get("access_token")
            if not access_token:
                return WriteResult(success=False, error="No access token")

            async with LinearClient(access_token) as client:
                if action == "create_issue":
                    # Required: team_id, title
                    team_id = data.get("team_id")
                    title = data.get("title")

                    if not team_id or not title:
                        return WriteResult(
                            success=False,
                            error="team_id and title are required for create_issue",
                        )

                    issue = await client.create_issue(
                        team_id=team_id,
                        title=title,
                        description=data.get("description"),
                        priority=data.get("priority"),
                        assignee_id=data.get("assignee_id"),
                        project_id=data.get("project_id"),
                        cycle_id=data.get("cycle_id"),
                        label_ids=data.get("label_ids"),
                    )

                    logger.info(
                        "linear_service.write_item.issue_created",
                        identifier=issue.get("identifier"),
                    )

                    return WriteResult(
                        success=True,
                        item_id=issue.get("id"),
                        external_id=issue.get("identifier"),
                        url=issue.get("url"),
                        data=issue,
                    )

                elif action == "update_issue":
                    issue_id = data.get("issue_id")
                    if not issue_id:
                        return WriteResult(
                            success=False, error="issue_id is required for update_issue"
                        )

                    issue = await client.update_issue(
                        issue_id=issue_id,
                        title=data.get("title"),
                        description=data.get("description"),
                        state_id=data.get("state_id"),
                        priority=data.get("priority"),
                        assignee_id=data.get("assignee_id"),
                    )

                    logger.info(
                        "linear_service.write_item.issue_updated",
                        identifier=issue.get("identifier"),
                    )

                    return WriteResult(
                        success=True,
                        item_id=issue.get("id"),
                        external_id=issue.get("identifier"),
                        data=issue,
                    )

                elif action == "update_status":
                    issue_id = data.get("issue_id")
                    state_id = data.get("state_id")

                    if not issue_id or not state_id:
                        return WriteResult(
                            success=False,
                            error="issue_id and state_id are required for update_status",
                        )

                    issue = await client.update_issue(
                        issue_id=issue_id, state_id=state_id
                    )

                    return WriteResult(
                        success=True,
                        item_id=issue.get("id"),
                        external_id=issue.get("identifier"),
                        data=issue,
                    )

                else:
                    return WriteResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("linear_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    def list_my_issues(
        cls,
        db: Session,
        user_id: str,
        assignee_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List issues assigned to the user.

        Args:
            db: Database session
            user_id: User ID
            assignee_name: Optional assignee name to filter by
            status: Optional status to filter by
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="issue",
            assignee=assignee_name,
            status=status,
            limit=limit,
        )

    @classmethod
    def search_issues(
        cls,
        db: Session,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        Search issues by query.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="issue",
            search_query=query,
            limit=limit,
        )

    @classmethod
    async def get_teams(
        cls,
        db: Session,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Linear teams for a user (for issue creation).

        Args:
            db: Database session
            user_id: User ID
            org_id: Optional org ID

        Returns:
            List of team dictionaries
        """
        try:
            connection = cls.get_connection(db, user_id, org_id)
            if not connection:
                return []

            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with LinearClient(access_token) as client:
                return await client.list_teams()

        except Exception as e:
            logger.error("linear_service.get_teams.error", error=str(e))
            return []
