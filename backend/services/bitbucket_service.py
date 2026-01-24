"""
Bitbucket service for NAVI integration.

Provides sync, query, and write operations for Bitbucket repositories, PRs, and pipelines.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    SyncResult,
    WriteResult,
)
from backend.integrations.bitbucket_client import BitbucketClient

logger = structlog.get_logger(__name__)


class BitbucketService(ConnectorServiceBase):
    """
    Bitbucket connector service for NAVI.

    Supports:
    - Repositories (list, search)
    - Pull Requests (list, create, comment)
    - Pipelines (list, status)
    - Issues (list)
    """

    PROVIDER = "bitbucket"
    SUPPORTED_ITEM_TYPES = ["repository", "pull_request", "pipeline", "issue"]
    WRITE_OPERATIONS = ["create_pr", "add_comment", "create_issue"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync repositories and PRs from Bitbucket to database.

        Args:
            db: Database session
            connection: Connection with credentials
            item_types: Optional list of types to sync (default: all)

        Returns:
            SyncResult with sync statistics
        """
        logger.info(
            "bitbucket_service.sync_items.start",
            connector_id=connection.get("id"),
            item_types=item_types,
        )

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for Bitbucket connection"
                )

            access_token = credentials.get("access_token")
            if not access_token:
                return SyncResult(
                    success=False, error="No access token in Bitbucket credentials"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            types_to_sync = item_types or ["repository", "pull_request"]

            async with BitbucketClient(access_token) as client:
                # Get current user
                user = await client.get_current_user()
                user.get("username", "")

                if "repository" in types_to_sync:
                    # Fetch user's repositories
                    repos_data = await client.list_repositories(pagelen=100)
                    repos = repos_data.get("values", [])

                    for repo in repos:
                        external_id = repo.get("uuid", "")
                        workspace = repo.get("workspace", {}).get("slug", "")
                        repo_slug = repo.get("slug", "")

                        data = {
                            "workspace": workspace,
                            "slug": repo_slug,
                            "full_name": repo.get("full_name"),
                            "is_private": repo.get("is_private"),
                            "language": repo.get("language"),
                            "mainbranch": repo.get("mainbranch"),
                            "size": repo.get("size"),
                            "has_issues": repo.get("has_issues"),
                            "has_wiki": repo.get("has_wiki"),
                        }

                        created_at = None
                        updated_at = None
                        if repo.get("created_on"):
                            try:
                                created_at = datetime.fromisoformat(
                                    repo["created_on"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass
                        if repo.get("updated_on"):
                            try:
                                updated_at = datetime.fromisoformat(
                                    repo["updated_on"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass

                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="repository",
                            external_id=external_id,
                            title=repo.get("name"),
                            description=repo.get("description"),
                            status="active",
                            url=repo.get("links", {}).get("html", {}).get("href"),
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                            external_created_at=created_at,
                            external_updated_at=updated_at,
                        )

                        items_synced += 1
                        if result == "created":
                            items_created += 1
                        else:
                            items_updated += 1

                if "pull_request" in types_to_sync:
                    # Fetch PRs from each repo
                    repos_data = await client.list_repositories(pagelen=50)
                    repos = repos_data.get("values", [])

                    for repo in repos:
                        workspace = repo.get("workspace", {}).get("slug", "")
                        repo_slug = repo.get("slug", "")

                        try:
                            prs_data = await client.list_pull_requests(
                                workspace=workspace,
                                repo_slug=repo_slug,
                                state="OPEN",
                                pagelen=50,
                            )
                            prs = prs_data.get("values", [])

                            for pr in prs:
                                external_id = str(pr.get("id", ""))
                                author = pr.get("author", {}).get("display_name", "")

                                data = {
                                    "workspace": workspace,
                                    "repo_slug": repo_slug,
                                    "author": author,
                                    "source_branch": pr.get("source", {})
                                    .get("branch", {})
                                    .get("name"),
                                    "destination_branch": pr.get("destination", {})
                                    .get("branch", {})
                                    .get("name"),
                                    "comment_count": pr.get("comment_count"),
                                    "task_count": pr.get("task_count"),
                                    "merge_commit": pr.get("merge_commit"),
                                }

                                created_at = None
                                updated_at = None
                                if pr.get("created_on"):
                                    try:
                                        created_at = datetime.fromisoformat(
                                            pr["created_on"].replace("Z", "+00:00")
                                        )
                                    except Exception:
                                        pass
                                if pr.get("updated_on"):
                                    try:
                                        updated_at = datetime.fromisoformat(
                                            pr["updated_on"].replace("Z", "+00:00")
                                        )
                                    except Exception:
                                        pass

                                result = cls.upsert_item(
                                    db=db,
                                    connector_id=connector_id,
                                    item_type="pull_request",
                                    external_id=f"{workspace}/{repo_slug}/{external_id}",
                                    title=pr.get("title"),
                                    description=pr.get("description"),
                                    status=pr.get("state", "OPEN"),
                                    url=pr.get("links", {}).get("html", {}).get("href"),
                                    assignee=author,
                                    user_id=user_id,
                                    org_id=org_id,
                                    data=data,
                                    external_created_at=created_at,
                                    external_updated_at=updated_at,
                                )

                                items_synced += 1
                                if result == "created":
                                    items_created += 1
                                else:
                                    items_updated += 1

                        except Exception as e:
                            logger.warning(
                                "bitbucket_service.sync_prs.error",
                                repo=f"{workspace}/{repo_slug}",
                                error=str(e),
                            )

            # Update sync status
            cls.update_sync_status(
                db=db,
                connector_id=connector_id,
                status="success",
            )

            logger.info(
                "bitbucket_service.sync_items.complete",
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("bitbucket_service.sync_items.error", error=str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        connection: Dict[str, Any],
        action: str,
        data: Dict[str, Any],
    ) -> WriteResult:
        """
        Perform write operation on Bitbucket.

        Args:
            db: Database session
            connection: Connection with credentials
            action: Action to perform (create_pr, add_comment, etc.)
            data: Data for the write operation

        Returns:
            WriteResult with operation result
        """
        logger.info(
            "bitbucket_service.write_item.start",
            connector_id=connection.get("id"),
            action=action,
        )

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(
                    success=False, error="No credentials found for Bitbucket connection"
                )

            access_token = credentials.get("access_token")
            if not access_token:
                return WriteResult(
                    success=False, error="No access token in Bitbucket credentials"
                )

            async with BitbucketClient(access_token) as client:
                if action == "add_comment":
                    # Add comment to PR
                    workspace = data.get("workspace")
                    repo_slug = data.get("repo_slug")
                    pr_id = data.get("pr_id")
                    content = data.get("content")

                    if not all([workspace, repo_slug, pr_id, content]):
                        return WriteResult(
                            success=False,
                            error="Missing required fields: workspace, repo_slug, pr_id, content",
                        )

                    # Bitbucket comment API endpoint
                    result = await client._post(
                        f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments",
                        {"content": {"raw": content}},
                    )

                    return WriteResult(
                        success=True,
                        item_id=str(result.get("id")),
                        url=result.get("links", {}).get("html", {}).get("href"),
                    )

                else:
                    return WriteResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("bitbucket_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    async def list_my_prs(
        cls,
        db: Session,
        connection: Dict[str, Any],
        status: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List pull requests authored by the current user.

        Args:
            db: Database session
            connection: Connection with credentials
            status: Filter by status (OPEN, MERGED, DECLINED)
            max_results: Maximum results to return

        Returns:
            List of PRs
        """
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            prs = []
            async with BitbucketClient(access_token) as client:
                user = await client.get_current_user()
                username = user.get("username", "")

                # Get user's repos
                repos_data = await client.list_repositories(pagelen=50)
                repos = repos_data.get("values", [])

                for repo in repos[:10]:  # Limit to first 10 repos
                    workspace = repo.get("workspace", {}).get("slug", "")
                    repo_slug = repo.get("slug", "")

                    try:
                        pr_state = status or "OPEN"
                        prs_data = await client.list_pull_requests(
                            workspace=workspace,
                            repo_slug=repo_slug,
                            state=pr_state,
                            pagelen=20,
                        )
                        repo_prs = prs_data.get("values", [])

                        # Filter to user's PRs
                        for pr in repo_prs:
                            author = pr.get("author", {}).get("username", "")
                            if author == username:
                                prs.append(
                                    {
                                        "id": pr.get("id"),
                                        "title": pr.get("title"),
                                        "description": pr.get("description"),
                                        "state": pr.get("state"),
                                        "url": pr.get("links", {})
                                        .get("html", {})
                                        .get("href"),
                                        "workspace": workspace,
                                        "repo_slug": repo_slug,
                                        "source_branch": pr.get("source", {})
                                        .get("branch", {})
                                        .get("name"),
                                        "destination_branch": pr.get("destination", {})
                                        .get("branch", {})
                                        .get("name"),
                                        "created_on": pr.get("created_on"),
                                        "updated_on": pr.get("updated_on"),
                                    }
                                )

                        if len(prs) >= max_results:
                            break

                    except Exception as e:
                        logger.warning(
                            "bitbucket_service.list_my_prs.repo_error",
                            repo=f"{workspace}/{repo_slug}",
                            error=str(e),
                        )

            return prs[:max_results]

        except Exception as e:
            logger.error("bitbucket_service.list_my_prs.error", error=str(e))
            return []

    @classmethod
    async def list_repos(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List repositories the user has access to.

        Args:
            db: Database session
            connection: Connection with credentials
            max_results: Maximum results to return

        Returns:
            List of repositories
        """
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with BitbucketClient(access_token) as client:
                repos_data = await client.list_repositories(pagelen=max_results)
                repos = repos_data.get("values", [])

                return [
                    {
                        "uuid": repo.get("uuid"),
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "slug": repo.get("slug"),
                        "workspace": repo.get("workspace", {}).get("slug"),
                        "description": repo.get("description"),
                        "is_private": repo.get("is_private"),
                        "language": repo.get("language"),
                        "url": repo.get("links", {}).get("html", {}).get("href"),
                        "updated_on": repo.get("updated_on"),
                    }
                    for repo in repos[:max_results]
                ]

        except Exception as e:
            logger.error("bitbucket_service.list_repos.error", error=str(e))
            return []

    @classmethod
    async def get_pipeline_status(
        cls,
        db: Session,
        connection: Dict[str, Any],
        workspace: str,
        repo_slug: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent pipeline statuses for a repository.

        Args:
            db: Database session
            connection: Connection with credentials
            workspace: Workspace slug
            repo_slug: Repository slug
            max_results: Maximum results to return

        Returns:
            List of pipeline statuses
        """
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with BitbucketClient(access_token) as client:
                pipelines_data = await client.list_pipelines(
                    workspace=workspace,
                    repo_slug=repo_slug,
                    pagelen=max_results,
                )
                pipelines = pipelines_data.get("values", [])

                return [
                    {
                        "uuid": pipeline.get("uuid"),
                        "build_number": pipeline.get("build_number"),
                        "state": pipeline.get("state", {}).get("name"),
                        "result": (
                            pipeline.get("state", {}).get("result", {}).get("name")
                            if pipeline.get("state", {}).get("result")
                            else None
                        ),
                        "creator": pipeline.get("creator", {}).get("display_name"),
                        "target": pipeline.get("target", {}).get("ref_name"),
                        "created_on": pipeline.get("created_on"),
                        "completed_on": pipeline.get("completed_on"),
                        "duration_in_seconds": pipeline.get("duration_in_seconds"),
                    }
                    for pipeline in pipelines[:max_results]
                ]

        except Exception as e:
            logger.error("bitbucket_service.get_pipeline_status.error", error=str(e))
            return []
