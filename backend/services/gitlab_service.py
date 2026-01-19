"""
GitLab service for NAVI integration.

Provides sync, query, and write operations for GitLab MRs, issues, and pipelines.
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
from backend.integrations.gitlab_client import GitLabClient

logger = structlog.get_logger(__name__)


class GitLabService(ConnectorServiceBase):
    """
    GitLab connector service for NAVI.

    Supports:
    - Merge Requests (list, search, create, comment)
    - Issues (list, search, create)
    - Pipelines (list status)
    - Projects (list)
    """

    PROVIDER = "gitlab"
    SUPPORTED_ITEM_TYPES = ["merge_request", "issue", "pipeline", "project"]
    WRITE_OPERATIONS = ["create_mr", "create_issue", "add_comment"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync merge requests, issues, and pipelines from GitLab to database.

        Args:
            db: Database session
            connection: Connection with credentials
            item_types: Optional list of types to sync (default: all)

        Returns:
            SyncResult with sync statistics
        """
        logger.info(
            "gitlab_service.sync_items.start",
            connector_id=connection.get("id"),
            item_types=item_types,
        )

        try:
            # Get credentials
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for GitLab connection"
                )

            access_token = credentials.get("access_token")
            base_url = credentials.get("base_url")

            if not access_token:
                return SyncResult(
                    success=False, error="No access token in GitLab credentials"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            types_to_sync = item_types or ["merge_request", "issue", "pipeline"]

            async with GitLabClient(access_token, base_url) as client:
                # Get current user for assignee matching
                current_user = await client.get_current_user()
                current_user.get("username", "")

                # Get projects first
                projects = await client.list_projects(membership=True, per_page=50)

                for project in projects:
                    project_id = project.get("id")
                    project_name = project.get("path_with_namespace", "")

                    if "merge_request" in types_to_sync:
                        # Fetch MRs
                        mrs = await client.list_merge_requests(
                            project_id, state="all", per_page=50
                        )

                        for mr in mrs:
                            external_id = str(mr.get("id"))

                            # Determine assignee
                            assignee = None
                            if mr.get("assignee"):
                                assignee = mr["assignee"].get("username")
                            elif mr.get("assignees"):
                                assignee = ", ".join(
                                    [a.get("username", "") for a in mr["assignees"]]
                                )

                            # Parse dates
                            created_at = None
                            updated_at = None
                            if mr.get("created_at"):
                                try:
                                    created_at = datetime.fromisoformat(
                                        mr["created_at"].replace("Z", "+00:00")
                                    )
                                except Exception:
                                    pass
                            if mr.get("updated_at"):
                                try:
                                    updated_at = datetime.fromisoformat(
                                        mr["updated_at"].replace("Z", "+00:00")
                                    )
                                except Exception:
                                    pass

                            # Build data dict
                            data = {
                                "iid": mr.get("iid"),
                                "project_id": project_id,
                                "project_name": project_name,
                                "source_branch": mr.get("source_branch"),
                                "target_branch": mr.get("target_branch"),
                                "author": mr.get("author"),
                                "labels": mr.get("labels", []),
                                "milestone": mr.get("milestone"),
                                "merge_status": mr.get("merge_status"),
                                "draft": mr.get("draft"),
                            }

                            result = cls.upsert_item(
                                db=db,
                                connector_id=connector_id,
                                item_type="merge_request",
                                external_id=external_id,
                                title=mr.get("title"),
                                description=mr.get("description"),
                                status=mr.get("state"),
                                url=mr.get("web_url"),
                                assignee=assignee,
                                user_id=user_id,
                                org_id=org_id,
                                data=data,
                                external_created_at=created_at,
                                external_updated_at=updated_at,
                            )

                            if result:
                                items_synced += 1

                    if "issue" in types_to_sync:
                        # Fetch issues
                        issues = await client.list_issues(
                            project_id, state="all", per_page=50
                        )

                        for issue in issues:
                            external_id = str(issue.get("id"))

                            # Determine assignee
                            assignee = None
                            if issue.get("assignee"):
                                assignee = issue["assignee"].get("username")
                            elif issue.get("assignees"):
                                assignee = ", ".join(
                                    [a.get("username", "") for a in issue["assignees"]]
                                )

                            # Parse dates
                            created_at = None
                            updated_at = None
                            if issue.get("created_at"):
                                try:
                                    created_at = datetime.fromisoformat(
                                        issue["created_at"].replace("Z", "+00:00")
                                    )
                                except Exception:
                                    pass
                            if issue.get("updated_at"):
                                try:
                                    updated_at = datetime.fromisoformat(
                                        issue["updated_at"].replace("Z", "+00:00")
                                    )
                                except Exception:
                                    pass

                            # Build data dict
                            data = {
                                "iid": issue.get("iid"),
                                "project_id": project_id,
                                "project_name": project_name,
                                "author": issue.get("author"),
                                "labels": issue.get("labels", []),
                                "milestone": issue.get("milestone"),
                                "weight": issue.get("weight"),
                            }

                            result = cls.upsert_item(
                                db=db,
                                connector_id=connector_id,
                                item_type="issue",
                                external_id=external_id,
                                title=issue.get("title"),
                                description=issue.get("description"),
                                status=issue.get("state"),
                                url=issue.get("web_url"),
                                assignee=assignee,
                                user_id=user_id,
                                org_id=org_id,
                                data=data,
                                external_created_at=created_at,
                                external_updated_at=updated_at,
                            )

                            if result:
                                items_synced += 1

                    if "pipeline" in types_to_sync:
                        # Fetch recent pipelines
                        pipelines = await client.list_pipelines(project_id, per_page=20)

                        for pipeline in pipelines:
                            external_id = str(pipeline.get("id"))

                            # Parse dates
                            created_at = None
                            updated_at = None
                            if pipeline.get("created_at"):
                                try:
                                    created_at = datetime.fromisoformat(
                                        pipeline["created_at"].replace("Z", "+00:00")
                                    )
                                except Exception:
                                    pass
                            if pipeline.get("updated_at"):
                                try:
                                    updated_at = datetime.fromisoformat(
                                        pipeline["updated_at"].replace("Z", "+00:00")
                                    )
                                except Exception:
                                    pass

                            data = {
                                "project_id": project_id,
                                "project_name": project_name,
                                "ref": pipeline.get("ref"),
                                "sha": pipeline.get("sha"),
                                "source": pipeline.get("source"),
                            }

                            result = cls.upsert_item(
                                db=db,
                                connector_id=connector_id,
                                item_type="pipeline",
                                external_id=external_id,
                                title=f"Pipeline #{pipeline.get('id')} - {pipeline.get('ref')}",
                                status=pipeline.get("status"),
                                url=pipeline.get("web_url"),
                                user_id=user_id,
                                org_id=org_id,
                                data=data,
                                external_created_at=created_at,
                                external_updated_at=updated_at,
                            )

                            if result:
                                items_synced += 1

                logger.info(
                    "gitlab_service.sync_items.projects_processed",
                    count=len(projects),
                )

            # Update connector sync status
            cls.update_sync_status(db, connector_id, "success")

            logger.info(
                "gitlab_service.sync_items.complete",
                items_synced=items_synced,
            )

            return SyncResult(
                success=True,
                items_synced=items_synced,
            )

        except Exception as e:
            logger.error("gitlab_service.sync_items.error", error=str(e))
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
        Write operation to GitLab (create MR, issue, comment).

        Args:
            db: Database session
            user_id: User performing the action
            item_type: Type of item
            action: Action to perform
            data: Data for the operation
            org_id: Optional organization ID

        Returns:
            WriteResult with success status
        """
        logger.info(
            "gitlab_service.write_item.start",
            user_id=user_id,
            item_type=item_type,
            action=action,
        )

        # Write operations not fully implemented yet - return placeholder
        return WriteResult(
            success=False, error="GitLab write operations not yet implemented"
        )

    @classmethod
    def list_my_merge_requests(
        cls,
        db: Session,
        user_id: str,
        assignee_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List merge requests assigned to or created by the user.

        Args:
            db: Database session
            user_id: User ID
            assignee_name: Optional assignee name to filter by
            status: Optional status filter (opened, closed, merged)
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="merge_request",
            assignee=assignee_name,
            status=status,
            limit=limit,
        )

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
        List GitLab issues assigned to the user.

        Args:
            db: Database session
            user_id: User ID
            assignee_name: Optional assignee name to filter by
            status: Optional status filter
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
    def get_pipeline_status(
        cls,
        db: Session,
        user_id: str,
        limit: int = 10,
    ) -> List[ConnectorItem]:
        """
        Get recent pipeline statuses.

        Args:
            db: Database session
            user_id: User ID
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="pipeline",
            limit=limit,
        )

    @classmethod
    def search_items(
        cls,
        db: Session,
        user_id: str,
        query: str,
        item_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        Search GitLab items by query.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            item_type: Optional item type filter
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type=item_type,
            search_query=query,
            limit=limit,
        )
