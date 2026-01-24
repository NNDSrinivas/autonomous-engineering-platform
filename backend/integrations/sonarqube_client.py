"""
SonarQube API client for code quality analysis.

Provides access to SonarQube projects, issues, measures, quality gates, and analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class SonarQubeClient:
    """
    Async SonarQube API client.

    Supports:
    - Projects and components
    - Issues (bugs, vulnerabilities, code smells)
    - Measures and metrics
    - Quality gates
    - Analysis history
    - Rules and profiles
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
    ):
        """
        Initialize SonarQube client.

        Args:
            base_url: SonarQube server URL (e.g., https://sonarqube.example.com)
            token: User token for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "SonarQubeClient":
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api",
            auth=(self.token, ""),  # Token as username, empty password
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    # -------------------------------------------------------------------------
    # System
    # -------------------------------------------------------------------------

    async def get_system_status(self) -> Dict[str, Any]:
        """Get SonarQube system status."""
        resp = await self.client.get("/system/status")
        resp.raise_for_status()
        return resp.json()

    async def get_system_health(self) -> Dict[str, Any]:
        """Get SonarQube system health."""
        resp = await self.client.get("/system/health")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def search_projects(
        self,
        query: Optional[str] = None,
        qualifiers: str = "TRK",
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Search for projects.

        Args:
            query: Search query
            qualifiers: Component qualifiers (TRK=projects, BRC=sub-projects)
            page: Page number
            page_size: Results per page

        Returns:
            Projects and paging info
        """
        params: Dict[str, Any] = {
            "qualifiers": qualifiers,
            "p": page,
            "ps": page_size,
        }
        if query:
            params["q"] = query

        resp = await self.client.get("/projects/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_project(
        self,
        project_key: str,
    ) -> Dict[str, Any]:
        """Get project details."""
        resp = await self.client.get(
            "/components/show",
            params={"component": project_key},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_project(
        self,
        project_key: str,
        name: str,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            project_key: Unique project key
            name: Project name
            visibility: public or private

        Returns:
            Created project
        """
        resp = await self.client.post(
            "/projects/create",
            data={
                "project": project_key,
                "name": name,
                "visibility": visibility,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_project(
        self,
        project_key: str,
    ) -> bool:
        """Delete a project."""
        resp = await self.client.post(
            "/projects/delete",
            data={"project": project_key},
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Issues
    # -------------------------------------------------------------------------

    async def search_issues(
        self,
        project_keys: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        assigned_to_me: bool = False,
        resolved: Optional[bool] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Search for issues.

        Args:
            project_keys: Filter by projects
            severities: BLOCKER, CRITICAL, MAJOR, MINOR, INFO
            types: BUG, VULNERABILITY, CODE_SMELL
            statuses: OPEN, CONFIRMED, REOPENED, RESOLVED, CLOSED
            tags: Filter by tags
            assigned_to_me: Only my issues
            resolved: True for resolved, False for unresolved
            created_after: ISO date
            created_before: ISO date
            page: Page number
            page_size: Results per page

        Returns:
            Issues and facets
        """
        params: Dict[str, Any] = {
            "p": page,
            "ps": page_size,
        }
        if project_keys:
            params["projects"] = ",".join(project_keys)
        if severities:
            params["severities"] = ",".join(severities)
        if types:
            params["types"] = ",".join(types)
        if statuses:
            params["statuses"] = ",".join(statuses)
        if tags:
            params["tags"] = ",".join(tags)
        if assigned_to_me:
            params["assignedToMe"] = "true"
        if resolved is not None:
            params["resolved"] = "true" if resolved else "false"
        if created_after:
            params["createdAfter"] = created_after
        if created_before:
            params["createdBefore"] = created_before

        resp = await self.client.get("/issues/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_issue(
        self,
        issue_key: str,
    ) -> Dict[str, Any]:
        """Get a single issue with details."""
        await self.search_issues()
        # SonarQube doesn't have a direct get issue endpoint
        # Use search with additional facets
        resp = await self.client.get(
            "/issues/search",
            params={
                "issues": issue_key,
                "additionalFields": "_all",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        return issues[0] if issues else {}

    async def assign_issue(
        self,
        issue_key: str,
        assignee: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assign an issue to a user."""
        data: Dict[str, str] = {"issue": issue_key}
        if assignee:
            data["assignee"] = assignee

        resp = await self.client.post("/issues/assign", data=data)
        resp.raise_for_status()
        return resp.json()

    async def add_issue_comment(
        self,
        issue_key: str,
        text: str,
    ) -> Dict[str, Any]:
        """Add a comment to an issue."""
        resp = await self.client.post(
            "/issues/add_comment",
            data={
                "issue": issue_key,
                "text": text,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def change_issue_severity(
        self,
        issue_key: str,
        severity: str,
    ) -> Dict[str, Any]:
        """Change issue severity."""
        resp = await self.client.post(
            "/issues/set_severity",
            data={
                "issue": issue_key,
                "severity": severity,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def change_issue_status(
        self,
        issue_key: str,
        transition: str,
    ) -> Dict[str, Any]:
        """
        Change issue status.

        Args:
            issue_key: Issue key
            transition: confirm, unconfirm, reopen, resolve, falsepositive, wontfix

        Returns:
            Updated issue
        """
        resp = await self.client.post(
            "/issues/do_transition",
            data={
                "issue": issue_key,
                "transition": transition,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def bulk_change_issues(
        self,
        issue_keys: List[str],
        assign: Optional[str] = None,
        set_severity: Optional[str] = None,
        set_type: Optional[str] = None,
        do_transition: Optional[str] = None,
        add_tags: Optional[List[str]] = None,
        remove_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Bulk change multiple issues."""
        data: Dict[str, str] = {
            "issues": ",".join(issue_keys),
        }
        if assign:
            data["assign"] = assign
        if set_severity:
            data["set_severity"] = set_severity
        if set_type:
            data["set_type"] = set_type
        if do_transition:
            data["do_transition"] = do_transition
        if add_tags:
            data["add_tags"] = ",".join(add_tags)
        if remove_tags:
            data["remove_tags"] = ",".join(remove_tags)

        resp = await self.client.post("/issues/bulk_change", data=data)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Measures
    # -------------------------------------------------------------------------

    async def get_component_measures(
        self,
        component: str,
        metric_keys: List[str],
        branch: Optional[str] = None,
        pull_request: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get measures for a component.

        Args:
            component: Component key
            metric_keys: Metrics to retrieve (e.g., bugs, vulnerabilities, code_smells)
            branch: Branch name
            pull_request: Pull request ID

        Returns:
            Component measures
        """
        params: Dict[str, Any] = {
            "component": component,
            "metricKeys": ",".join(metric_keys),
        }
        if branch:
            params["branch"] = branch
        if pull_request:
            params["pullRequest"] = pull_request

        resp = await self.client.get("/measures/component", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_measures_history(
        self,
        component: str,
        metrics: List[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get measures history for a component."""
        params: Dict[str, Any] = {
            "component": component,
            "metrics": ",".join(metrics),
            "p": page,
            "ps": page_size,
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        resp = await self.client.get("/measures/search_history", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Quality Gates
    # -------------------------------------------------------------------------

    async def list_quality_gates(self) -> Dict[str, Any]:
        """List all quality gates."""
        resp = await self.client.get("/qualitygates/list")
        resp.raise_for_status()
        return resp.json()

    async def get_quality_gate(
        self,
        gate_id: Optional[str] = None,
        gate_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get quality gate details."""
        params: Dict[str, str] = {}
        if gate_id:
            params["id"] = gate_id
        if gate_name:
            params["name"] = gate_name

        resp = await self.client.get("/qualitygates/show", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_project_quality_gate_status(
        self,
        project_key: str,
        branch: Optional[str] = None,
        pull_request: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get quality gate status for a project."""
        params: Dict[str, str] = {"projectKey": project_key}
        if branch:
            params["branch"] = branch
        if pull_request:
            params["pullRequest"] = pull_request

        resp = await self.client.get("/qualitygates/project_status", params=params)
        resp.raise_for_status()
        return resp.json()

    async def set_project_quality_gate(
        self,
        project_key: str,
        gate_name: str,
    ) -> bool:
        """Set quality gate for a project."""
        resp = await self.client.post(
            "/qualitygates/select",
            data={
                "projectKey": project_key,
                "gateName": gate_name,
            },
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Analysis
    # -------------------------------------------------------------------------

    async def get_project_analyses(
        self,
        project: str,
        branch: Optional[str] = None,
        category: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Get project analysis history.

        Args:
            project: Project key
            branch: Branch name
            category: Event category filter
            from_date: ISO date
            to_date: ISO date
            page: Page number
            page_size: Results per page

        Returns:
            Analysis history
        """
        params: Dict[str, Any] = {
            "project": project,
            "p": page,
            "ps": page_size,
        }
        if branch:
            params["branch"] = branch
        if category:
            params["category"] = category
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        resp = await self.client.get("/project_analyses/search", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Rules
    # -------------------------------------------------------------------------

    async def search_rules(
        self,
        languages: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
        activation: Optional[str] = None,
        qprofile: Optional[str] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Search for rules."""
        params: Dict[str, Any] = {
            "p": page,
            "ps": page_size,
        }
        if languages:
            params["languages"] = ",".join(languages)
        if tags:
            params["tags"] = ",".join(tags)
        if types:
            params["types"] = ",".join(types)
        if severities:
            params["severities"] = ",".join(severities)
        if activation:
            params["activation"] = activation
        if qprofile:
            params["qprofile"] = qprofile
        if query:
            params["q"] = query

        resp = await self.client.get("/rules/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_rule(
        self,
        rule_key: str,
    ) -> Dict[str, Any]:
        """Get rule details."""
        resp = await self.client.get(
            "/rules/show",
            params={"key": rule_key},
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Quality Profiles
    # -------------------------------------------------------------------------

    async def search_quality_profiles(
        self,
        language: Optional[str] = None,
        project: Optional[str] = None,
        quality_profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for quality profiles."""
        params: Dict[str, str] = {}
        if language:
            params["language"] = language
        if project:
            params["project"] = project
        if quality_profile:
            params["qualityProfile"] = quality_profile

        resp = await self.client.get("/qualityprofiles/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def add_project_to_profile(
        self,
        project: str,
        quality_profile: str,
        language: str,
    ) -> bool:
        """Add a project to a quality profile."""
        resp = await self.client.post(
            "/qualityprofiles/add_project",
            data={
                "project": project,
                "qualityProfile": quality_profile,
                "language": language,
            },
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Hotspots (Security)
    # -------------------------------------------------------------------------

    async def search_hotspots(
        self,
        project_key: str,
        status: Optional[str] = None,
        resolution: Optional[str] = None,
        branch: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Search for security hotspots.

        Args:
            project_key: Project key
            status: TO_REVIEW, REVIEWED
            resolution: FIXED, SAFE, ACKNOWLEDGED
            branch: Branch name
            page: Page number
            page_size: Results per page

        Returns:
            Security hotspots
        """
        params: Dict[str, Any] = {
            "projectKey": project_key,
            "p": page,
            "ps": page_size,
        }
        if status:
            params["status"] = status
        if resolution:
            params["resolution"] = resolution
        if branch:
            params["branch"] = branch

        resp = await self.client.get("/hotspots/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_hotspot(
        self,
        hotspot_key: str,
    ) -> Dict[str, Any]:
        """Get security hotspot details."""
        resp = await self.client.get(
            "/hotspots/show",
            params={"hotspot": hotspot_key},
        )
        resp.raise_for_status()
        return resp.json()

    async def change_hotspot_status(
        self,
        hotspot_key: str,
        status: str,
        resolution: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Change security hotspot status.

        Args:
            hotspot_key: Hotspot key
            status: TO_REVIEW or REVIEWED
            resolution: FIXED, SAFE, or ACKNOWLEDGED (required if REVIEWED)
            comment: Optional comment

        Returns:
            Success boolean
        """
        data: Dict[str, str] = {
            "hotspot": hotspot_key,
            "status": status,
        }
        if resolution:
            data["resolution"] = resolution
        if comment:
            data["comment"] = comment

        resp = await self.client.post("/hotspots/change_status", data=data)
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Source Code
    # -------------------------------------------------------------------------

    async def get_source_lines(
        self,
        component: str,
        from_line: int = 1,
        to_line: int = 500,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get source code lines for a file."""
        params: Dict[str, Any] = {
            "key": component,
            "from": from_line,
            "to": to_line,
        }
        if branch:
            params["branch"] = branch

        resp = await self.client.get("/sources/lines", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_scm_info(
        self,
        component: str,
        from_line: int = 1,
        to_line: int = 500,
    ) -> Dict[str, Any]:
        """Get SCM (blame) info for a file."""
        resp = await self.client.get(
            "/sources/scm",
            params={
                "key": component,
                "from": from_line,
                "to": to_line,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List webhooks."""
        params: Dict[str, str] = {}
        if project:
            params["project"] = project

        resp = await self.client.get("/webhooks/list", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        name: str,
        url: str,
        project: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a webhook."""
        data: Dict[str, str] = {
            "name": name,
            "url": url,
        }
        if project:
            data["project"] = project
        if secret:
            data["secret"] = secret

        resp = await self.client.post("/webhooks/create", data=data)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(
        self,
        webhook_key: str,
    ) -> bool:
        """Delete a webhook."""
        resp = await self.client.post(
            "/webhooks/delete",
            data={"webhook": webhook_key},
        )
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def get_project_summary(
        self,
        project_key: str,
    ) -> Dict[str, Any]:
        """Get a summary of project quality metrics."""
        metrics = [
            "bugs",
            "vulnerabilities",
            "code_smells",
            "security_hotspots",
            "coverage",
            "duplicated_lines_density",
            "ncloc",
            "sqale_rating",
            "reliability_rating",
            "security_rating",
            "sqale_index",
            "alert_status",
        ]

        measures = await self.get_component_measures(project_key, metrics)
        quality_gate = await self.get_project_quality_gate_status(project_key)

        return {
            "project_key": project_key,
            "measures": measures,
            "quality_gate": quality_gate,
        }

    def format_rating(self, rating: str) -> str:
        """Convert numeric rating to letter grade."""
        rating_map = {
            "1.0": "A",
            "2.0": "B",
            "3.0": "C",
            "4.0": "D",
            "5.0": "E",
        }
        return rating_map.get(rating, rating)

    def get_severity_priority(self, severity: str) -> int:
        """Get numeric priority for severity (for sorting)."""
        priority_map = {
            "BLOCKER": 1,
            "CRITICAL": 2,
            "MAJOR": 3,
            "MINOR": 4,
            "INFO": 5,
        }
        return priority_map.get(severity, 99)
