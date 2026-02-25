"""Enhanced Jira client for NAVI memory integration

This client extends the existing Jira service with methods specifically
for ingesting issues into NAVI's conversational memory system.
"""

import os
from typing import List, Dict, Any, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


class JiraClient:
    """
    Jira REST API client for AEP NAVI memory integration.

    Uses email + API token auth (basic auth with Atlassian API token).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        access_token: Optional[str] = None,
        token_type: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("AEP_JIRA_BASE_URL", "")).rstrip("/")
        self.email = email or os.getenv("AEP_JIRA_EMAIL", "")
        self.api_token = api_token or os.getenv("AEP_JIRA_API_TOKEN", "")
        self.access_token = access_token
        self.token_type = token_type or "Bearer"

        if not self.base_url:
            raise RuntimeError(
                "JiraClient is not configured. Set AEP_JIRA_BASE_URL or pass base_url."
            )

        use_bearer = bool(self.access_token)
        if not use_bearer and (not self.email or not self.api_token):
            raise RuntimeError(
                "JiraClient is not configured. "
                "Provide access_token (OAuth) or AEP_JIRA_EMAIL + AEP_JIRA_API_TOKEN."
            )

        headers = {"Accept": "application/json"}
        auth = None
        if use_bearer:
            token_type = (self.token_type or "Bearer").strip()
            headers["Authorization"] = f"{token_type} {self.access_token}"
        else:
            auth = (self.email, self.api_token)

        self.client = httpx.AsyncClient(headers=headers, auth=auth, timeout=30.0)

        logger.info("JiraClient initialized", base_url=self.base_url)

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated GET request to Jira API"""
        url = f"{self.base_url}{path}"
        try:
            resp = await self.client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Jira API error",
                url=url,
                status=e.response.status_code,
                error=e.response.text[:200],
            )
            raise RuntimeError(
                f"Jira GET {url} failed: {e.response.status_code} {e.response.text[:200]}"
            )
        except Exception as e:
            logger.error("Jira request failed", url=url, error=str(e))
            raise

    async def get_assigned_issues(
        self,
        jql: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fetch issues assigned to the current Jira user or via custom JQL.

        Args:
            jql: Custom JQL query (default: assigned to current user, not done)
            max_results: Maximum number of issues to return

        Returns:
            List of issue dictionaries with fields
        """
        jql = (
            jql
            or "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
        )

        logger.info("Fetching Jira issues", jql=jql, max_results=max_results)

        data = await self._get(
            "/rest/api/3/search/jql",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,description,status,assignee,priority,issuetype,created,updated",
            },
        )

        issues = data.get("issues", [])
        logger.info(f"Fetched {len(issues)} Jira issues")

        return issues

    async def get_issue(self, key: str) -> Dict[str, Any]:
        """
        Fetch a single issue by key, e.g. ABC-123.

        Args:
            key: Jira issue key (e.g., "ENG-102")

        Returns:
            Issue dictionary with all fields
        """
        logger.info("Fetching Jira issue", key=key)
        return await self._get(f"/rest/api/3/issue/{key}")

    async def get_myself(self) -> Dict[str, Any]:
        """
        Fetch the current Jira user profile to validate credentials.
        """
        logger.info("Fetching Jira current user profile")
        return await self._get("/rest/api/3/myself")

    async def get_issues_by_project(
        self,
        project_key: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch issues for a specific project.

        Args:
            project_key: Jira project key (e.g., "ENG")
            max_results: Maximum number of issues

        Returns:
            List of issue dictionaries
        """
        jql = f"project = {project_key} ORDER BY updated DESC"
        return await self.get_assigned_issues(jql=jql, max_results=max_results)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()
        logger.info("JiraClient closed")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
