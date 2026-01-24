"""GitLab API client for AEP connector integration.

Supports:
- Project listing and details
- Merge requests
- Issues
- CI/CD pipelines
- User information
"""

from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


class GitLabClient:
    """
    GitLab API client for AEP NAVI integration.

    Supports both GitLab.com and self-hosted GitLab instances.
    """

    DEFAULT_BASE_URL = "https://gitlab.com"

    def __init__(
        self,
        access_token: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_url = f"{self.base_url}/api/v4"
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("GitLabClient initialized", base_url=self.base_url)

    async def __aenter__(self) -> "GitLabClient":
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
        """Make a GET request to the GitLab API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.api_url}{endpoint}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a POST request to the GitLab API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.api_url}{endpoint}"
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # User Methods
    # -------------------------------------------------------------------------

    async def get_current_user(self) -> Dict[str, Any]:
        """
        Get the currently authenticated user.

        Returns:
            User information including id, username, email, name
        """
        user = await self._get("/user")
        logger.info("GitLab user fetched", username=user.get("username"))
        return user

    # -------------------------------------------------------------------------
    # Project Methods
    # -------------------------------------------------------------------------

    async def list_projects(
        self,
        membership: bool = True,
        per_page: int = 100,
        page: int = 1,
        order_by: str = "last_activity_at",
        sort: str = "desc",
    ) -> List[Dict[str, Any]]:
        """
        List projects accessible to the authenticated user.

        Args:
            membership: If True, only show projects the user is a member of
            per_page: Number of results per page (max 100)
            page: Page number
            order_by: Order by field (id, name, path, created_at, updated_at, last_activity_at)
            sort: Sort direction (asc, desc)

        Returns:
            List of project dictionaries
        """
        params = {
            "membership": str(membership).lower(),
            "per_page": per_page,
            "page": page,
            "order_by": order_by,
            "sort": sort,
        }
        projects = await self._get("/projects", params=params)
        logger.info("GitLab projects listed", count=len(projects))
        return projects

    async def get_project(self, project_id: int | str) -> Dict[str, Any]:
        """
        Get a single project by ID or URL-encoded path.

        Args:
            project_id: Project ID or URL-encoded path (e.g., 'namespace%2Fproject')

        Returns:
            Project details
        """
        return await self._get(f"/projects/{project_id}")

    # -------------------------------------------------------------------------
    # Merge Request Methods
    # -------------------------------------------------------------------------

    async def list_merge_requests(
        self,
        project_id: int | str,
        state: str = "opened",
        per_page: int = 50,
        page: int = 1,
        scope: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        List merge requests for a project.

        Args:
            project_id: Project ID or URL-encoded path
            state: MR state (opened, closed, merged, all)
            per_page: Number of results per page
            page: Page number
            scope: Scope (all, created_by_me, assigned_to_me)

        Returns:
            List of merge request dictionaries
        """
        params = {
            "state": state,
            "per_page": per_page,
            "page": page,
            "scope": scope,
        }
        mrs = await self._get(f"/projects/{project_id}/merge_requests", params=params)
        logger.info("GitLab MRs listed", project_id=project_id, count=len(mrs))
        return mrs

    async def get_merge_request(
        self,
        project_id: int | str,
        mr_iid: int,
    ) -> Dict[str, Any]:
        """
        Get a single merge request.

        Args:
            project_id: Project ID or URL-encoded path
            mr_iid: Merge request IID (internal ID)

        Returns:
            Merge request details
        """
        return await self._get(f"/projects/{project_id}/merge_requests/{mr_iid}")

    async def get_merge_request_changes(
        self,
        project_id: int | str,
        mr_iid: int,
    ) -> Dict[str, Any]:
        """
        Get merge request changes (diff).

        Args:
            project_id: Project ID or URL-encoded path
            mr_iid: Merge request IID

        Returns:
            Merge request with changes/diffs included
        """
        return await self._get(
            f"/projects/{project_id}/merge_requests/{mr_iid}/changes"
        )

    # -------------------------------------------------------------------------
    # Issue Methods
    # -------------------------------------------------------------------------

    async def list_issues(
        self,
        project_id: int | str,
        state: str = "opened",
        per_page: int = 50,
        page: int = 1,
        scope: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        List issues for a project.

        Args:
            project_id: Project ID or URL-encoded path
            state: Issue state (opened, closed, all)
            per_page: Number of results per page
            page: Page number
            scope: Scope (all, created_by_me, assigned_to_me)

        Returns:
            List of issue dictionaries
        """
        params = {
            "state": state,
            "per_page": per_page,
            "page": page,
            "scope": scope,
        }
        issues = await self._get(f"/projects/{project_id}/issues", params=params)
        logger.info("GitLab issues listed", project_id=project_id, count=len(issues))
        return issues

    async def get_issue(
        self,
        project_id: int | str,
        issue_iid: int,
    ) -> Dict[str, Any]:
        """
        Get a single issue.

        Args:
            project_id: Project ID or URL-encoded path
            issue_iid: Issue IID (internal ID)

        Returns:
            Issue details
        """
        return await self._get(f"/projects/{project_id}/issues/{issue_iid}")

    # -------------------------------------------------------------------------
    # Pipeline Methods
    # -------------------------------------------------------------------------

    async def list_pipelines(
        self,
        project_id: int | str,
        status: Optional[str] = None,
        per_page: int = 50,
        page: int = 1,
        ref: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List pipelines for a project.

        Args:
            project_id: Project ID or URL-encoded path
            status: Pipeline status filter (running, pending, success, failed, canceled, skipped, created, manual)
            per_page: Number of results per page
            page: Page number
            ref: Branch or tag name to filter by

        Returns:
            List of pipeline dictionaries
        """
        params: Dict[str, Any] = {
            "per_page": per_page,
            "page": page,
        }
        if status:
            params["status"] = status
        if ref:
            params["ref"] = ref

        pipelines = await self._get(f"/projects/{project_id}/pipelines", params=params)
        logger.info(
            "GitLab pipelines listed", project_id=project_id, count=len(pipelines)
        )
        return pipelines

    async def get_pipeline(
        self,
        project_id: int | str,
        pipeline_id: int,
    ) -> Dict[str, Any]:
        """
        Get a single pipeline.

        Args:
            project_id: Project ID or URL-encoded path
            pipeline_id: Pipeline ID

        Returns:
            Pipeline details
        """
        return await self._get(f"/projects/{project_id}/pipelines/{pipeline_id}")

    async def list_pipeline_jobs(
        self,
        project_id: int | str,
        pipeline_id: int,
        per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List jobs for a pipeline.

        Args:
            project_id: Project ID or URL-encoded path
            pipeline_id: Pipeline ID
            per_page: Number of results per page

        Returns:
            List of job dictionaries
        """
        params = {"per_page": per_page}
        return await self._get(
            f"/projects/{project_id}/pipelines/{pipeline_id}/jobs",
            params=params,
        )

    # -------------------------------------------------------------------------
    # Webhook Methods
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        project_id: int | str,
    ) -> List[Dict[str, Any]]:
        """
        List webhooks for a project.

        Args:
            project_id: Project ID or URL-encoded path

        Returns:
            List of webhook dictionaries
        """
        return await self._get(f"/projects/{project_id}/hooks")

    async def create_webhook(
        self,
        project_id: int | str,
        url: str,
        token: Optional[str] = None,
        push_events: bool = True,
        merge_requests_events: bool = True,
        issues_events: bool = True,
        pipeline_events: bool = True,
        enable_ssl_verification: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a webhook for a project.

        Args:
            project_id: Project ID or URL-encoded path
            url: Webhook URL
            token: Secret token for webhook verification
            push_events: Trigger on push events
            merge_requests_events: Trigger on MR events
            issues_events: Trigger on issue events
            pipeline_events: Trigger on pipeline events
            enable_ssl_verification: Enable SSL verification

        Returns:
            Created webhook details
        """
        data = {
            "url": url,
            "push_events": push_events,
            "merge_requests_events": merge_requests_events,
            "issues_events": issues_events,
            "pipeline_events": pipeline_events,
            "enable_ssl_verification": enable_ssl_verification,
        }
        if token:
            data["token"] = token

        webhook = await self._post(f"/projects/{project_id}/hooks", data=data)
        logger.info(
            "GitLab webhook created",
            project_id=project_id,
            webhook_id=webhook.get("id"),
        )
        return webhook

    # -------------------------------------------------------------------------
    # Repository Methods
    # -------------------------------------------------------------------------

    async def list_branches(
        self,
        project_id: int | str,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List branches for a project.

        Args:
            project_id: Project ID or URL-encoded path
            per_page: Number of results per page

        Returns:
            List of branch dictionaries
        """
        params = {"per_page": per_page}
        return await self._get(
            f"/projects/{project_id}/repository/branches", params=params
        )

    async def get_file(
        self,
        project_id: int | str,
        file_path: str,
        ref: str = "main",
    ) -> Dict[str, Any]:
        """
        Get a file from the repository.

        Args:
            project_id: Project ID or URL-encoded path
            file_path: Path to the file (URL-encoded)
            ref: Branch name, tag, or commit SHA

        Returns:
            File content and metadata
        """
        import urllib.parse

        encoded_path = urllib.parse.quote(file_path, safe="")
        params = {"ref": ref}
        return await self._get(
            f"/projects/{project_id}/repository/files/{encoded_path}",
            params=params,
        )
