"""Bitbucket API client for AEP connector integration.

Supports both Bitbucket Cloud (bitbucket.org) and Bitbucket Server.

Supports:
- Repositories
- Pull requests
- Commits
- Pipelines (Cloud only)
- Users
"""

from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


class BitbucketClient:
    """
    Bitbucket API client for AEP NAVI integration.

    Supports Bitbucket Cloud (bitbucket.org) with OAuth2.
    """

    CLOUD_API_URL = "https://api.bitbucket.org/2.0"

    def __init__(
        self,
        access_token: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.api_url = base_url.rstrip("/") if base_url else self.CLOUD_API_URL
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("BitbucketClient initialized", api_url=self.api_url)

    async def __aenter__(self) -> "BitbucketClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a GET request to the Bitbucket API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        url = f"{self.api_url}{endpoint}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a POST request to the Bitbucket API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        url = f"{self.api_url}{endpoint}"
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    async def _put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a PUT request to the Bitbucket API."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        url = f"{self.api_url}{endpoint}"
        response = await self._client.put(url, json=data)
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # User Methods
    # -------------------------------------------------------------------------

    async def get_current_user(self) -> Dict[str, Any]:
        """
        Get the currently authenticated user.

        Returns:
            User information including uuid, username, display_name
        """
        user = await self._get("/user")
        logger.info("Bitbucket user fetched", username=user.get("username"))
        return user

    async def get_user_emails(self) -> List[Dict[str, Any]]:
        """
        Get email addresses for the current user.

        Returns:
            List of email dictionaries
        """
        data = await self._get("/user/emails")
        return data.get("values", [])

    # -------------------------------------------------------------------------
    # Workspace Methods
    # -------------------------------------------------------------------------

    async def list_workspaces(
        self,
        page: int = 1,
        pagelen: int = 50,
    ) -> Dict[str, Any]:
        """
        List workspaces the user has access to.

        Args:
            page: Page number
            pagelen: Results per page

        Returns:
            Paginated workspace list
        """
        params = {"page": page, "pagelen": pagelen}
        data = await self._get("/workspaces", params=params)
        workspaces = data.get("values", [])
        logger.info("Bitbucket workspaces listed", count=len(workspaces))
        return data

    async def get_workspace(self, workspace: str) -> Dict[str, Any]:
        """
        Get a workspace by slug.

        Args:
            workspace: Workspace slug

        Returns:
            Workspace details
        """
        return await self._get(f"/workspaces/{workspace}")

    # -------------------------------------------------------------------------
    # Repository Methods
    # -------------------------------------------------------------------------

    async def list_repositories(
        self,
        workspace: Optional[str] = None,
        page: int = 1,
        pagelen: int = 50,
        sort: str = "-updated_on",
        role: str = "member",
    ) -> Dict[str, Any]:
        """
        List repositories.

        Args:
            workspace: Optional workspace to filter by
            page: Page number
            pagelen: Results per page
            sort: Sort field (prefix with - for descending)
            role: Filter by role (member, contributor, admin, owner)

        Returns:
            Paginated repository list
        """
        params: Dict[str, Any] = {
            "page": page,
            "pagelen": pagelen,
            "sort": sort,
        }

        if workspace:
            endpoint = f"/repositories/{workspace}"
        else:
            endpoint = "/repositories"
            params["role"] = role

        data = await self._get(endpoint, params=params)
        repos = data.get("values", [])
        logger.info("Bitbucket repositories listed", count=len(repos))
        return data

    async def get_repository(
        self,
        workspace: str,
        repo_slug: str,
    ) -> Dict[str, Any]:
        """
        Get a repository by workspace and slug.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug

        Returns:
            Repository details
        """
        return await self._get(f"/repositories/{workspace}/{repo_slug}")

    # -------------------------------------------------------------------------
    # Pull Request Methods
    # -------------------------------------------------------------------------

    async def list_pull_requests(
        self,
        workspace: str,
        repo_slug: str,
        state: str = "OPEN",
        page: int = 1,
        pagelen: int = 50,
    ) -> Dict[str, Any]:
        """
        List pull requests for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            state: PR state (OPEN, MERGED, DECLINED, SUPERSEDED)
            page: Page number
            pagelen: Results per page

        Returns:
            Paginated pull request list
        """
        params = {
            "state": state,
            "page": page,
            "pagelen": pagelen,
        }
        data = await self._get(
            f"/repositories/{workspace}/{repo_slug}/pullrequests",
            params=params,
        )
        prs = data.get("values", [])
        logger.info(
            "Bitbucket PRs listed",
            workspace=workspace,
            repo=repo_slug,
            count=len(prs),
        )
        return data

    async def get_pull_request(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: int,
    ) -> Dict[str, Any]:
        """
        Get a pull request.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            pr_id: Pull request ID

        Returns:
            Pull request details
        """
        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
        )

    async def get_pull_request_diff(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: int,
    ) -> str:
        """
        Get pull request diff.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            pr_id: Pull request ID

        Returns:
            Diff as string
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        url = f"{self.api_url}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
        response = await self._client.get(url)
        response.raise_for_status()
        return response.text

    async def list_pull_request_comments(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: int,
        page: int = 1,
        pagelen: int = 100,
    ) -> Dict[str, Any]:
        """
        List comments on a pull request.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            pr_id: Pull request ID
            page: Page number
            pagelen: Results per page

        Returns:
            Paginated comment list
        """
        params = {"page": page, "pagelen": pagelen}
        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments",
            params=params,
        )

    # -------------------------------------------------------------------------
    # Commit Methods
    # -------------------------------------------------------------------------

    async def list_commits(
        self,
        workspace: str,
        repo_slug: str,
        branch: Optional[str] = None,
        page: int = 1,
        pagelen: int = 50,
    ) -> Dict[str, Any]:
        """
        List commits for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            branch: Optional branch to filter by
            page: Page number
            pagelen: Results per page

        Returns:
            Paginated commit list
        """
        params: Dict[str, Any] = {"page": page, "pagelen": pagelen}
        if branch:
            params["include"] = branch

        data = await self._get(
            f"/repositories/{workspace}/{repo_slug}/commits",
            params=params,
        )
        commits = data.get("values", [])
        logger.info(
            "Bitbucket commits listed",
            workspace=workspace,
            repo=repo_slug,
            count=len(commits),
        )
        return data

    async def get_commit(
        self,
        workspace: str,
        repo_slug: str,
        commit_hash: str,
    ) -> Dict[str, Any]:
        """
        Get a commit.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            commit_hash: Commit SHA

        Returns:
            Commit details
        """
        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/commit/{commit_hash}"
        )

    # -------------------------------------------------------------------------
    # Branch Methods
    # -------------------------------------------------------------------------

    async def list_branches(
        self,
        workspace: str,
        repo_slug: str,
        page: int = 1,
        pagelen: int = 100,
    ) -> Dict[str, Any]:
        """
        List branches for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            page: Page number
            pagelen: Results per page

        Returns:
            Paginated branch list
        """
        params = {"page": page, "pagelen": pagelen}
        data = await self._get(
            f"/repositories/{workspace}/{repo_slug}/refs/branches",
            params=params,
        )
        branches = data.get("values", [])
        logger.info(
            "Bitbucket branches listed",
            workspace=workspace,
            repo=repo_slug,
            count=len(branches),
        )
        return data

    # -------------------------------------------------------------------------
    # Pipeline Methods (Bitbucket Cloud only)
    # -------------------------------------------------------------------------

    async def list_pipelines(
        self,
        workspace: str,
        repo_slug: str,
        page: int = 1,
        pagelen: int = 50,
        sort: str = "-created_on",
    ) -> Dict[str, Any]:
        """
        List pipelines for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            page: Page number
            pagelen: Results per page
            sort: Sort field

        Returns:
            Paginated pipeline list
        """
        params = {
            "page": page,
            "pagelen": pagelen,
            "sort": sort,
        }
        data = await self._get(
            f"/repositories/{workspace}/{repo_slug}/pipelines",
            params=params,
        )
        pipelines = data.get("values", [])
        logger.info(
            "Bitbucket pipelines listed",
            workspace=workspace,
            repo=repo_slug,
            count=len(pipelines),
        )
        return data

    async def get_pipeline(
        self,
        workspace: str,
        repo_slug: str,
        pipeline_uuid: str,
    ) -> Dict[str, Any]:
        """
        Get a pipeline.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            pipeline_uuid: Pipeline UUID (with or without braces)

        Returns:
            Pipeline details
        """
        # Ensure UUID has braces
        if not pipeline_uuid.startswith("{"):
            pipeline_uuid = f"{{{pipeline_uuid}}}"

        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/pipelines/{pipeline_uuid}"
        )

    async def list_pipeline_steps(
        self,
        workspace: str,
        repo_slug: str,
        pipeline_uuid: str,
    ) -> Dict[str, Any]:
        """
        List steps for a pipeline.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            pipeline_uuid: Pipeline UUID

        Returns:
            Pipeline steps
        """
        if not pipeline_uuid.startswith("{"):
            pipeline_uuid = f"{{{pipeline_uuid}}}"

        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/pipelines/{pipeline_uuid}/steps"
        )

    # -------------------------------------------------------------------------
    # Webhook Methods
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        workspace: str,
        repo_slug: str,
    ) -> Dict[str, Any]:
        """
        List webhooks for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug

        Returns:
            Webhook list
        """
        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/hooks"
        )

    async def create_webhook(
        self,
        workspace: str,
        repo_slug: str,
        url: str,
        description: str = "AEP NAVI Webhook",
        events: Optional[List[str]] = None,
        active: bool = True,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            url: Webhook URL
            description: Webhook description
            events: List of events to subscribe to
            active: Whether webhook is active
            secret: Optional secret for HMAC signing

        Returns:
            Created webhook details
        """
        if events is None:
            events = [
                "repo:push",
                "pullrequest:created",
                "pullrequest:updated",
                "pullrequest:approved",
                "pullrequest:unapproved",
                "pullrequest:fulfilled",
                "pullrequest:rejected",
                "pullrequest:comment_created",
                "issue:created",
                "issue:updated",
            ]

        data: Dict[str, Any] = {
            "description": description,
            "url": url,
            "active": active,
            "events": events,
        }
        if secret:
            data["secret"] = secret

        webhook = await self._post(
            f"/repositories/{workspace}/{repo_slug}/hooks",
            data,
        )
        logger.info(
            "Bitbucket webhook created",
            workspace=workspace,
            repo=repo_slug,
            webhook_uuid=webhook.get("uuid"),
        )
        return webhook

    async def delete_webhook(
        self,
        workspace: str,
        repo_slug: str,
        webhook_uuid: str,
    ) -> None:
        """
        Delete a webhook.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            webhook_uuid: Webhook UUID
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        # Ensure UUID has braces
        if not webhook_uuid.startswith("{"):
            webhook_uuid = f"{{{webhook_uuid}}}"

        url = f"{self.api_url}/repositories/{workspace}/{repo_slug}/hooks/{webhook_uuid}"
        response = await self._client.delete(url)
        response.raise_for_status()
        logger.info(
            "Bitbucket webhook deleted",
            workspace=workspace,
            repo=repo_slug,
            webhook_uuid=webhook_uuid,
        )

    # -------------------------------------------------------------------------
    # Issue Methods
    # -------------------------------------------------------------------------

    async def list_issues(
        self,
        workspace: str,
        repo_slug: str,
        state: Optional[str] = None,
        page: int = 1,
        pagelen: int = 50,
    ) -> Dict[str, Any]:
        """
        List issues for a repository.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            state: Issue state (new, open, resolved, on hold, invalid, duplicate, wontfix, closed)
            page: Page number
            pagelen: Results per page

        Returns:
            Paginated issue list
        """
        params: Dict[str, Any] = {"page": page, "pagelen": pagelen}
        if state:
            params["q"] = f'state="{state}"'

        data = await self._get(
            f"/repositories/{workspace}/{repo_slug}/issues",
            params=params,
        )
        issues = data.get("values", [])
        logger.info(
            "Bitbucket issues listed",
            workspace=workspace,
            repo=repo_slug,
            count=len(issues),
        )
        return data

    async def get_issue(
        self,
        workspace: str,
        repo_slug: str,
        issue_id: int,
    ) -> Dict[str, Any]:
        """
        Get an issue.

        Args:
            workspace: Workspace slug
            repo_slug: Repository slug
            issue_id: Issue ID

        Returns:
            Issue details
        """
        return await self._get(
            f"/repositories/{workspace}/{repo_slug}/issues/{issue_id}"
        )
