"""
Web Tools for NAVI

Tools for fetching and analyzing web content:
- fetch_url: Fetch and parse content from a URL
- search_web: Search the web using configured search API

These tools allow NAVI to access external web resources when users
provide links or need information from the web.
"""

import re
import html
import logging
import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TIMEOUT = 30.0
MAX_CONTENT_LENGTH = 100_000  # 100KB max content to return
USER_AGENT = "NAVI-Bot/1.0 (Autonomous Engineering Platform)"

# Optional: Tavily API for web search
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_API_URL = "https://api.tavily.com/search"


def _clean_html(html_content: str) -> str:
    """
    Extract readable text from HTML content.

    Uses regex-based extraction for simplicity and no extra dependencies.
    """
    # Remove script and style elements
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"<noscript[^>]*>.*?</noscript>", "", text, flags=re.DOTALL | re.IGNORECASE
    )

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Extract title
    title_match = re.search(
        r"<title[^>]*>(.*?)</title>", text, flags=re.DOTALL | re.IGNORECASE
    )
    title = html.unescape(title_match.group(1).strip()) if title_match else ""

    # Extract meta description
    desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
        text,
        flags=re.IGNORECASE,
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']',
            text,
            flags=re.IGNORECASE,
        )
    description = html.unescape(desc_match.group(1).strip()) if desc_match else ""

    # Convert common block elements to newlines
    text = re.sub(r"<(br|hr)[^>]*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</(p|div|h[1-6]|li|tr|article|section|header|footer)>",
        "\n\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<(p|div|h[1-6]|li|tr|article|section|header|footer)[^>]*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    # Extract link text with URL for important links
    def replace_link(match):
        href = match.group(1)
        link_text = re.sub(r"<[^>]+>", "", match.group(2))
        if (
            href
            and link_text
            and not href.startswith("#")
            and not href.startswith("javascript:")
        ):
            return f"{link_text}"
        return link_text

    text = re.sub(
        r'<a[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>',
        replace_link,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single space
    text = re.sub(r"\n[ \t]+", "\n", text)  # Remove leading whitespace from lines
    text = re.sub(r"[ \t]+\n", "\n", text)  # Remove trailing whitespace from lines
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 consecutive newlines
    text = text.strip()

    # Combine title, description, and content
    result_parts = []
    if title:
        result_parts.append(f"# {title}\n")
    if description:
        result_parts.append(f"> {description}\n")
    if text:
        result_parts.append(text)

    return "\n".join(result_parts)


def _is_valid_url(url: str) -> bool:
    """Validate URL format and scheme."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


async def fetch_url(
    user_id: str,
    url: str,
    extract_text: bool = True,
    max_length: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetch content from a URL and optionally extract readable text.

    Args:
        user_id: User ID executing the tool
        url: The URL to fetch
        extract_text: If True, extract readable text from HTML (default True)
        max_length: Maximum content length to return (default 100KB)

    Returns:
        {
            "success": bool,
            "message": str,
            "url": str,
            "title": str (if HTML),
            "content": str,
            "content_type": str,
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:web.fetch_url] user={user_id}, url={url}")

    # Validate URL
    if not url:
        return {
            "success": False,
            "message": "No URL provided",
            "error": "URL is required",
        }

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not _is_valid_url(url):
        return {
            "success": False,
            "message": f"Invalid URL: `{url}`",
            "error": "Invalid URL format",
        }

    max_len = max_length or MAX_CONTENT_LENGTH

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()

            # Check if response is too large
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_len * 2:
                return {
                    "success": False,
                    "message": f"Content too large: {int(content_length)} bytes",
                    "url": url,
                    "error": "Content exceeds maximum size limit",
                }

            # Get content
            raw_content = response.text

            # Extract text from HTML if requested
            if extract_text and "html" in content_type:
                content = _clean_html(raw_content)
                # Extract title for response
                title_match = re.search(r"# (.*?)\n", content)
                title = title_match.group(1) if title_match else ""
            else:
                content = raw_content
                title = ""

            # Truncate if too long
            if len(content) > max_len:
                content = (
                    content[:max_len]
                    + f"\n\n[... Content truncated at {max_len} characters ...]"
                )

            return {
                "success": True,
                "message": f"Fetched `{url}` ({len(content)} chars)",
                "url": str(response.url),  # Final URL after redirects
                "title": title,
                "content": content,
                "content_type": content_type,
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "message": f"Request timed out: `{url}`",
            "url": url,
            "error": "Request timed out",
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "message": f"HTTP error {e.response.status_code}: `{url}`",
            "url": url,
            "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "message": f"Request failed: `{url}`",
            "url": url,
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"[TOOL:web.fetch_url] Error: {e}")
        return {
            "success": False,
            "message": f"Error fetching URL: {str(e)}",
            "url": url,
            "error": str(e),
        }


async def search_web(
    user_id: str,
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> Dict[str, Any]:
    """
    Search the web using Tavily API.

    Requires TAVILY_API_KEY environment variable to be set.

    Args:
        user_id: User ID executing the tool
        query: Search query
        max_results: Maximum number of results (default 5, max 10)
        search_depth: "basic" or "advanced" (default "basic")

    Returns:
        {
            "success": bool,
            "message": str,
            "query": str,
            "results": List[{title, url, content, score}],
            "error": str (if failure)
        }
    """
    logger.info(f"[TOOL:web.search] user={user_id}, query={query}")

    if not query:
        return {
            "success": False,
            "message": "No search query provided",
            "error": "Query is required",
        }

    if not TAVILY_API_KEY:
        return {
            "success": False,
            "message": "Web search is not configured. Set TAVILY_API_KEY environment variable.",
            "query": query,
            "error": "TAVILY_API_KEY not configured",
        }

    max_results = min(max_results, 10)  # Cap at 10

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                TAVILY_API_URL,
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_answer": True,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                        "score": item.get("score", 0),
                    }
                )

            answer = data.get("answer", "")

            return {
                "success": True,
                "message": f"Found {len(results)} results for: `{query}`",
                "query": query,
                "answer": answer,
                "results": results,
            }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "message": f"Search API error: {e.response.status_code}",
            "query": query,
            "error": f"HTTP {e.response.status_code}",
        }
    except Exception as e:
        logger.error(f"[TOOL:web.search] Error: {e}")
        return {
            "success": False,
            "message": f"Search failed: {str(e)}",
            "query": query,
            "error": str(e),
        }
