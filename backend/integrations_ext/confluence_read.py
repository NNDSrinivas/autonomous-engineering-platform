"""Confluence Read Connector - read-only access to Confluence pages"""

import logging
import httpx
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


def _safe_nested_get(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely extract nested dictionary values with fallback.

    Traverses nested dictionaries using the provided keys, returning the default
    value if any key is missing or returns a non-dict value (except for the final key).

    Args:
        data: The dictionary to traverse
        *keys: The sequence of keys to follow (e.g., "body", "storage", "value")
        default: The value to return if any key is missing (default: None)

    Returns:
        The value at the nested path, or the default value

    Examples:
        >>> _safe_nested_get({"a": {"b": {"c": 123}}}, "a", "b", "c")
        123
        >>> _safe_nested_get({"a": {}}, "a", "b", "c", default="fallback")
        'fallback'
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _extract_results(response_json: dict, space_key: str) -> List[Dict]:
    """
    Extract results from Confluence API response.

    Handles multiple API response formats with explicit fallback logic:
    1. Nested structure: response['page']['results']
    2. Direct structure: response['results']
    3. Empty fallback: []

    Args:
        response_json: The JSON response from Confluence API
        space_key: The space key for logging context (helps identify which space
                   has unexpected response structure during debugging)

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
        if page_results is not None and isinstance(page_results, list):
            return page_results

    # Try direct results structure
    if "results" in response_json:
        direct_results = response_json.get("results")
        if direct_results is not None and isinstance(direct_results, list):
            return direct_results

    # Return empty list as fallback
    logger.warning(
        "Unexpected Confluence API response structure for space %s: results not found or not a list",
        space_key,
    )
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

            # Extract nested body.storage.value using safe helper
            body = _safe_nested_get(p, "body", "storage", "value", default="")

            url = f"{self.base}/pages/{pid}"

            # Extract nested version.number using safe helper
            ver = _safe_nested_get(p, "version", "number", default=1)

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
