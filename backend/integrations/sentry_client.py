"""
Sentry API client for error tracking and performance monitoring.

Provides access to Sentry organizations, projects, issues, events, and releases.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class SentryClient:
    """
    Async Sentry API client.

    Supports:
    - Organizations and teams
    - Projects
    - Issues and events
    - Releases and deployments
    - Performance monitoring
    - Alerts and notifications
    """

    BASE_URL = "https://sentry.io/api/0"

    def __init__(
        self,
        auth_token: str,
        organization_slug: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Sentry client.

        Args:
            auth_token: Sentry auth token (org-level or user-level)
            organization_slug: Default organization slug
            timeout: Request timeout in seconds
        """
        self.auth_token = auth_token
        self.organization_slug = organization_slug
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "SentryClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
            },
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

    def _org_slug(self, org_slug: Optional[str]) -> str:
        """Get organization slug with fallback to default."""
        slug = org_slug or self.organization_slug
        if not slug:
            raise ValueError("Organization slug required")
        return slug

    # -------------------------------------------------------------------------
    # Organizations
    # -------------------------------------------------------------------------

    async def list_organizations(self) -> List[Dict[str, Any]]:
        """List organizations the token has access to."""
        resp = await self.client.get("/organizations/")
        resp.raise_for_status()
        return resp.json()

    async def get_organization(
        self,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get organization details."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/organizations/{slug}/")
        resp.raise_for_status()
        return resp.json()

    async def get_organization_stats(
        self,
        org_slug: Optional[str] = None,
        stat: str = "received",
        since: Optional[int] = None,
        until: Optional[int] = None,
        resolution: str = "1h",
    ) -> List[List[int]]:
        """
        Get organization statistics.

        Args:
            org_slug: Organization slug
            stat: Stat type (received, rejected, blacklisted)
            since: Start timestamp
            until: End timestamp
            resolution: Time resolution (1h, 1d, etc.)

        Returns:
            List of [timestamp, count] pairs
        """
        slug = self._org_slug(org_slug)
        params: Dict[str, Any] = {
            "stat": stat,
            "resolution": resolution,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        resp = await self.client.get(f"/organizations/{slug}/stats/", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Teams
    # -------------------------------------------------------------------------

    async def list_teams(
        self,
        org_slug: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List teams in an organization."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/organizations/{slug}/teams/")
        resp.raise_for_status()
        return resp.json()

    async def get_team(
        self,
        team_slug: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get team details."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/teams/{slug}/{team_slug}/")
        resp.raise_for_status()
        return resp.json()

    async def create_team(
        self,
        name: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new team."""
        slug = self._org_slug(org_slug)
        resp = await self.client.post(
            f"/organizations/{slug}/teams/",
            json={"name": name},
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    async def list_projects(
        self,
        org_slug: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List projects in an organization."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/organizations/{slug}/projects/")
        resp.raise_for_status()
        return resp.json()

    async def get_project(
        self,
        project_slug: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get project details."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/projects/{slug}/{project_slug}/")
        resp.raise_for_status()
        return resp.json()

    async def create_project(
        self,
        name: str,
        team_slug: str,
        platform: Optional[str] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name
            team_slug: Team to assign project to
            platform: Platform (python, javascript, etc.)
            org_slug: Organization slug

        Returns:
            Created project
        """
        slug = self._org_slug(org_slug)
        payload: Dict[str, Any] = {"name": name}
        if platform:
            payload["platform"] = platform

        resp = await self.client.post(
            f"/teams/{slug}/{team_slug}/projects/",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_project(
        self,
        project_slug: str,
        org_slug: Optional[str] = None,
    ) -> bool:
        """Delete a project."""
        slug = self._org_slug(org_slug)
        resp = await self.client.delete(f"/projects/{slug}/{project_slug}/")
        return resp.status_code == 204

    async def get_project_stats(
        self,
        project_slug: str,
        stat: str = "received",
        since: Optional[int] = None,
        until: Optional[int] = None,
        resolution: str = "1h",
        org_slug: Optional[str] = None,
    ) -> List[List[int]]:
        """Get project statistics."""
        slug = self._org_slug(org_slug)
        params: Dict[str, Any] = {
            "stat": stat,
            "resolution": resolution,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        resp = await self.client.get(
            f"/projects/{slug}/{project_slug}/stats/",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Issues
    # -------------------------------------------------------------------------

    async def list_issues(
        self,
        project_slug: Optional[str] = None,
        query: Optional[str] = None,
        sort: str = "date",
        statsPeriod: str = "24h",
        cursor: Optional[str] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List issues.

        Args:
            project_slug: Filter by project
            query: Search query (Sentry search syntax)
            sort: Sort by (date, new, priority, freq, user)
            statsPeriod: Time period for stats (24h, 14d, etc.)
            cursor: Pagination cursor
            org_slug: Organization slug

        Returns:
            Issues with pagination
        """
        slug = self._org_slug(org_slug)
        params: Dict[str, Any] = {
            "sort": sort,
            "statsPeriod": statsPeriod,
        }
        if project_slug:
            params["project"] = project_slug
        if query:
            params["query"] = query
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/organizations/{slug}/issues/", params=params)
        resp.raise_for_status()

        # Extract pagination from Link header
        link_header = resp.headers.get("Link", "")
        next_cursor = self._parse_link_header(link_header, "next")

        return {
            "issues": resp.json(),
            "next_cursor": next_cursor,
        }

    async def get_issue(
        self,
        issue_id: str,
    ) -> Dict[str, Any]:
        """Get issue details."""
        resp = await self.client.get(f"/issues/{issue_id}/")
        resp.raise_for_status()
        return resp.json()

    async def update_issue(
        self,
        issue_id: str,
        status: Optional[str] = None,
        assignedTo: Optional[str] = None,
        hasSeen: Optional[bool] = None,
        isBookmarked: Optional[bool] = None,
        isSubscribed: Optional[bool] = None,
        isPublic: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update an issue.

        Args:
            issue_id: Issue ID
            status: resolved, unresolved, ignored
            assignedTo: User ID or team slug
            hasSeen: Mark as seen
            isBookmarked: Bookmark status
            isSubscribed: Subscribe status
            isPublic: Public status

        Returns:
            Updated issue
        """
        payload: Dict[str, Any] = {}
        if status:
            payload["status"] = status
        if assignedTo:
            payload["assignedTo"] = assignedTo
        if hasSeen is not None:
            payload["hasSeen"] = hasSeen
        if isBookmarked is not None:
            payload["isBookmarked"] = isBookmarked
        if isSubscribed is not None:
            payload["isSubscribed"] = isSubscribed
        if isPublic is not None:
            payload["isPublic"] = isPublic

        resp = await self.client.put(f"/issues/{issue_id}/", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_issue(
        self,
        issue_id: str,
    ) -> bool:
        """Delete an issue."""
        resp = await self.client.delete(f"/issues/{issue_id}/")
        return resp.status_code == 202

    async def get_issue_events(
        self,
        issue_id: str,
        full: bool = False,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get events for an issue."""
        params: Dict[str, Any] = {}
        if full:
            params["full"] = "true"
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/issues/{issue_id}/events/", params=params)
        resp.raise_for_status()

        link_header = resp.headers.get("Link", "")
        next_cursor = self._parse_link_header(link_header, "next")

        return {
            "events": resp.json(),
            "next_cursor": next_cursor,
        }

    async def get_issue_hashes(
        self,
        issue_id: str,
    ) -> List[Dict[str, Any]]:
        """Get hashes for an issue."""
        resp = await self.client.get(f"/issues/{issue_id}/hashes/")
        resp.raise_for_status()
        return resp.json()

    async def get_issue_tags(
        self,
        issue_id: str,
    ) -> List[Dict[str, Any]]:
        """Get tags for an issue."""
        resp = await self.client.get(f"/issues/{issue_id}/tags/")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    async def get_event(
        self,
        event_id: str,
        project_slug: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get event details."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(
            f"/projects/{slug}/{project_slug}/events/{event_id}/"
        )
        resp.raise_for_status()
        return resp.json()

    async def get_latest_event(
        self,
        issue_id: str,
    ) -> Dict[str, Any]:
        """Get the latest event for an issue."""
        resp = await self.client.get(f"/issues/{issue_id}/events/latest/")
        resp.raise_for_status()
        return resp.json()

    async def get_oldest_event(
        self,
        issue_id: str,
    ) -> Dict[str, Any]:
        """Get the oldest event for an issue."""
        resp = await self.client.get(f"/issues/{issue_id}/events/oldest/")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Releases
    # -------------------------------------------------------------------------

    async def list_releases(
        self,
        project_slug: Optional[str] = None,
        query: Optional[str] = None,
        cursor: Optional[str] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List releases."""
        slug = self._org_slug(org_slug)
        params: Dict[str, Any] = {}
        if project_slug:
            params["project"] = project_slug
        if query:
            params["query"] = query
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/organizations/{slug}/releases/", params=params)
        resp.raise_for_status()

        link_header = resp.headers.get("Link", "")
        next_cursor = self._parse_link_header(link_header, "next")

        return {
            "releases": resp.json(),
            "next_cursor": next_cursor,
        }

    async def get_release(
        self,
        version: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get release details."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/organizations/{slug}/releases/{version}/")
        resp.raise_for_status()
        return resp.json()

    async def create_release(
        self,
        version: str,
        projects: List[str],
        ref: Optional[str] = None,
        url: Optional[str] = None,
        dateReleased: Optional[str] = None,
        commits: Optional[List[Dict[str, Any]]] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new release.

        Args:
            version: Release version string
            projects: Project slugs to associate
            ref: Optional ref (git sha)
            url: Optional URL
            dateReleased: ISO date of release
            commits: List of commit objects
            org_slug: Organization slug

        Returns:
            Created release
        """
        slug = self._org_slug(org_slug)
        payload: Dict[str, Any] = {
            "version": version,
            "projects": projects,
        }
        if ref:
            payload["ref"] = ref
        if url:
            payload["url"] = url
        if dateReleased:
            payload["dateReleased"] = dateReleased
        if commits:
            payload["commits"] = commits

        resp = await self.client.post(f"/organizations/{slug}/releases/", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_release(
        self,
        version: str,
        ref: Optional[str] = None,
        url: Optional[str] = None,
        dateReleased: Optional[str] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a release."""
        slug = self._org_slug(org_slug)
        payload: Dict[str, Any] = {}
        if ref:
            payload["ref"] = ref
        if url:
            payload["url"] = url
        if dateReleased:
            payload["dateReleased"] = dateReleased

        resp = await self.client.put(
            f"/organizations/{slug}/releases/{version}/",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_release(
        self,
        version: str,
        org_slug: Optional[str] = None,
    ) -> bool:
        """Delete a release."""
        slug = self._org_slug(org_slug)
        resp = await self.client.delete(f"/organizations/{slug}/releases/{version}/")
        return resp.status_code == 204

    # -------------------------------------------------------------------------
    # Deployments
    # -------------------------------------------------------------------------

    async def list_deployments(
        self,
        version: str,
        org_slug: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List deployments for a release."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(
            f"/organizations/{slug}/releases/{version}/deploys/"
        )
        resp.raise_for_status()
        return resp.json()

    async def create_deployment(
        self,
        version: str,
        environment: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        dateStarted: Optional[str] = None,
        dateFinished: Optional[str] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a deployment.

        Args:
            version: Release version
            environment: Deployment environment (production, staging, etc.)
            name: Deployment name
            url: Deployment URL
            dateStarted: ISO date started
            dateFinished: ISO date finished
            org_slug: Organization slug

        Returns:
            Created deployment
        """
        slug = self._org_slug(org_slug)
        payload: Dict[str, Any] = {"environment": environment}
        if name:
            payload["name"] = name
        if url:
            payload["url"] = url
        if dateStarted:
            payload["dateStarted"] = dateStarted
        if dateFinished:
            payload["dateFinished"] = dateFinished

        resp = await self.client.post(
            f"/organizations/{slug}/releases/{version}/deploys/",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Alerts
    # -------------------------------------------------------------------------

    async def list_alert_rules(
        self,
        project_slug: str,
        org_slug: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List alert rules for a project."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/projects/{slug}/{project_slug}/rules/")
        resp.raise_for_status()
        return resp.json()

    async def get_alert_rule(
        self,
        project_slug: str,
        rule_id: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get alert rule details."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(
            f"/projects/{slug}/{project_slug}/rules/{rule_id}/"
        )
        resp.raise_for_status()
        return resp.json()

    async def create_alert_rule(
        self,
        project_slug: str,
        name: str,
        conditions: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        action_match: str = "all",
        frequency: int = 30,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an alert rule.

        Args:
            project_slug: Project slug
            name: Rule name
            conditions: List of condition objects
            actions: List of action objects
            action_match: all or any
            frequency: Minutes between alerts
            org_slug: Organization slug

        Returns:
            Created rule
        """
        slug = self._org_slug(org_slug)
        payload = {
            "name": name,
            "conditions": conditions,
            "actions": actions,
            "actionMatch": action_match,
            "frequency": frequency,
        }

        resp = await self.client.post(
            f"/projects/{slug}/{project_slug}/rules/",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Performance (Transactions)
    # -------------------------------------------------------------------------

    async def get_transaction_events(
        self,
        project_slug: str,
        transaction: str,
        statsPeriod: str = "24h",
        cursor: Optional[str] = None,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get transaction events."""
        slug = self._org_slug(org_slug)
        params: Dict[str, Any] = {
            "field": ["id", "timestamp", "transaction.duration", "trace"],
            "query": f'transaction:"{transaction}"',
            "statsPeriod": statsPeriod,
        }
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(
            f"/organizations/{slug}/events/",
            params=params,
        )
        resp.raise_for_status()

        link_header = resp.headers.get("Link", "")
        next_cursor = self._parse_link_header(link_header, "next")

        return {
            "events": resp.json(),
            "next_cursor": next_cursor,
        }

    # -------------------------------------------------------------------------
    # User Feedback
    # -------------------------------------------------------------------------

    async def list_user_feedback(
        self,
        project_slug: str,
        org_slug: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List user feedback for a project."""
        slug = self._org_slug(org_slug)
        resp = await self.client.get(f"/projects/{slug}/{project_slug}/user-feedback/")
        resp.raise_for_status()
        return resp.json()

    async def submit_user_feedback(
        self,
        project_slug: str,
        event_id: str,
        name: str,
        email: str,
        comments: str,
        org_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit user feedback for an event."""
        slug = self._org_slug(org_slug)
        resp = await self.client.post(
            f"/projects/{slug}/{project_slug}/user-feedback/",
            json={
                "event_id": event_id,
                "name": name,
                "email": email,
                "comments": comments,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _parse_link_header(self, link_header: str, rel: str) -> Optional[str]:
        """Parse Link header to extract cursor."""
        if not link_header:
            return None

        for link in link_header.split(","):
            parts = link.strip().split(";")
            if len(parts) < 2:
                continue

            url_part = parts[0].strip()
            rel_part = parts[1].strip()

            if f'rel="{rel}"' in rel_part:
                # Extract cursor from URL
                if "cursor=" in url_part:
                    import re

                    match = re.search(r"cursor=([^&>]+)", url_part)
                    if match:
                        return match.group(1)

        return None

    async def get_issue_summary(
        self,
        issue_id: str,
    ) -> Dict[str, Any]:
        """Get a summary of an issue with recent events."""
        issue = await self.get_issue(issue_id)
        events = await self.get_issue_events(issue_id)
        tags = await self.get_issue_tags(issue_id)

        return {
            "issue": issue,
            "recent_events": events.get("events", [])[:5],
            "tags": tags,
        }

    def format_error_message(self, event: Dict[str, Any]) -> str:
        """Format event into readable error message."""
        entries = event.get("entries", [])
        for entry in entries:
            if entry.get("type") == "exception":
                exception_data = entry.get("data", {})
                values = exception_data.get("values", [])
                if values:
                    exc = values[-1]
                    exc_type = exc.get("type", "Error")
                    exc_value = exc.get("value", "")
                    return f"{exc_type}: {exc_value}"

        return event.get("title", "Unknown error")
