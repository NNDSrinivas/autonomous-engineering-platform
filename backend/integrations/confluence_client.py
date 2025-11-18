"""Confluence client for NAVI memory integration

This client fetches pages and spaces from Confluence Cloud
and prepares them for ingestion into NAVI's memory system.
"""

import os
import re
from typing import List, Dict, Any, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ConfluenceClient:
    """
    Confluence REST API client for AEP NAVI memory integration.

    Uses email + API token auth (basic auth with Atlassian API token).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("AEP_CONFLUENCE_BASE_URL", "")).rstrip(
            "/"
        )
        self.email = email or os.getenv("AEP_CONFLUENCE_EMAIL", "")
        self.api_token = api_token or os.getenv("AEP_CONFLUENCE_API_TOKEN", "")

        if not self.base_url or not self.email or not self.api_token:
            raise RuntimeError(
                "ConfluenceClient is not configured. "
                "Set AEP_CONFLUENCE_BASE_URL, AEP_CONFLUENCE_EMAIL, AEP_CONFLUENCE_API_TOKEN."
            )

        self.client = httpx.AsyncClient(
            auth=(self.email, self.api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

        logger.info("ConfluenceClient initialized", base_url=self.base_url)

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated GET request to Confluence API"""
        url = f"{self.base_url}{path}"
        try:
            resp = await self.client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Confluence API error",
                url=url,
                status=e.response.status_code,
                error=e.response.text[:200],
            )
            raise RuntimeError(
                f"Confluence GET {url} failed: {e.response.status_code} {e.response.text[:200]}"
            )
        except Exception as e:
            logger.error("Confluence request failed", url=url, error=str(e))
            raise

    async def get_pages_in_space(
        self,
        space_key: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch pages in a given Confluence space with content body.

        Args:
            space_key: Confluence space key (e.g., "ENG", "DOCS")
            limit: Maximum number of pages to fetch

        Returns:
            List of page dictionaries with content
        """
        logger.info("Fetching Confluence pages", space_key=space_key, limit=limit)

        data = await self._get(
            "/rest/api/content",
            params={
                "spaceKey": space_key,
                "type": "page",
                "limit": limit,
                "expand": "body.storage,version,space",
            },
        )

        pages = data.get("results", [])
        logger.info(f"Fetched {len(pages)} Confluence pages from space {space_key}")

        return pages

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Fetch a single Confluence page by ID.

        Args:
            page_id: Confluence page ID

        Returns:
            Page dictionary with full content
        """
        logger.info("Fetching Confluence page", page_id=page_id)
        return await self._get(
            f"/rest/api/content/{page_id}",
            params={"expand": "body.storage,version,space"},
        )

    async def search_pages(
        self,
        cql: str,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Search Confluence pages using CQL (Confluence Query Language).

        Args:
            cql: CQL query string (e.g., "type=page AND space=ENG")
            limit: Maximum number of results

        Returns:
            List of matching page dictionaries
        """
        logger.info("Searching Confluence pages", cql=cql, limit=limit)

        data = await self._get(
            "/rest/api/content/search",
            params={
                "cql": cql,
                "limit": limit,
                "expand": "body.storage,version,space",
            },
        )

        results = data.get("results", [])
        logger.info(f"Found {len(results)} pages matching CQL query")

        return results

    @staticmethod
    def html_to_text(html: str) -> str:
        """
        Convert Confluence HTML/XHTML content to plain text.

        This is a simple implementation - for production, consider using
        a proper HTML parser like BeautifulSoup.

        Args:
            html: HTML content from Confluence

        Returns:
            Plain text version
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()
        logger.info("ConfluenceClient closed")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
