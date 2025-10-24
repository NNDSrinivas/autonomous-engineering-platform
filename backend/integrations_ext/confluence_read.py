"""Confluence Read Connector - read-only access to Confluence pages"""

import logging
import httpx
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _extract_results(response_json: dict, space_key: str) -> List[Dict]:
    """
    Extract results from Confluence API response.

    Handles multiple API response formats with explicit fallback logic:
    1. Nested structure: response['page']['results']
    2. Direct structure: response['results']
    3. Empty fallback: []

    Args:
        response_json: The JSON response from Confluence API
        space_key: The space key for logging context

    Returns:
        List of page results
    """
    has_page_key = "page" in response_json
    has_results_key = "results" in response_json
    logger.debug(
        "Confluence API response structure for space %s: page=%s, results=%s",
        space_key,
        has_page_key,
        has_results_key,
    )

    # Try nested page.results structure first
    page_obj = response_json.get("page")
    if page_obj and isinstance(page_obj, dict):
        page_results = page_obj.get("results")
        if page_results is not None:
            return page_results

    # Try direct results structure
    if "results" in response_json:
        direct_results = response_json.get("results")
        if direct_results is not None:
            return direct_results

    # Return empty list as fallback
    return []


class ConfluenceReader:
    def __init__(self, base_url: str, token: str, email: Optional[str] = None):
        self.base = base_url.rstrip("/")
        self.token = token
        self.email = email

    async def pages(
        self,
        client: httpx.AsyncClient,
        space_key: str,
        start=0,
        limit=100,
    ) -> List[Dict]:
        """Fetch pages from a Confluence space with pagination"""
        auth = {"Authorization": f"Basic {self.token}"}
        r = await client.get(
            f"{self.base}/rest/api/space/{space_key}/content",
            headers=auth,
            params={"start": start, "limit": limit, "expand": "body.storage,version"},
        )
        r.raise_for_status()
        j = r.json()
        # Use helper function to extract results with proper fallback logic
        results = _extract_results(j, space_key)

        out = []
        for p in results:
            title = p.get("title")
            pid = p.get("id")
            body = ((p.get("body") or {}).get("storage") or {}).get("value", "")
            url = f"{self.base}/pages/{pid}"
            ver = ((p.get("version") or {}).get("number")) or 1
            out.append(
                {
                    "id": pid,
                    "title": title,
                    "url": url,
                    "html": body,
                    "version": ver,
                }
            )
        return out
