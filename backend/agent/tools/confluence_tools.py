"""
Confluence tools for NAVI agent.

Provides tools to search and retrieve Confluence pages and documentation.
"""

from typing import Any, Dict
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def search_confluence_pages(
    context: Dict[str, Any],
    query: str,
    max_results: int = 20,
) -> ToolResult:
    """Search Confluence pages by content."""
    from backend.services.confluence_service import ConfluenceService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "confluence")

        if not connection:
            return ToolResult(
                output="Confluence is not connected. Please connect your Confluence account first.",
                sources=[],
            )

        pages = await ConfluenceService.search_pages(
            db=db, connection=connection, query=query, max_results=max_results
        )

        if not pages:
            return ToolResult(
                output=f"No Confluence pages found matching '{query}'.",
                sources=[],
            )

        lines = [f"Found {len(pages)} Confluence page(s) matching '{query}':\n"]
        sources = []

        for page in pages:
            title = page.get("title", "Untitled")
            space = page.get("space_name") or page.get("space_key", "")
            url = page.get("url", "")
            excerpt = page.get("excerpt", "")

            lines.append(f"- **{title}**")
            lines.append(f"  - Space: {space}")
            if excerpt:
                lines.append(f"  - {excerpt}...")
            if url:
                lines.append(f"  - [Open in Confluence]({url})")
            lines.append("")

            if url:
                sources.append({"type": "confluence_page", "name": title, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("search_confluence_pages.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_confluence_page(
    context: Dict[str, Any],
    page_id: str,
) -> ToolResult:
    """Get content of a specific Confluence page."""
    from backend.services.confluence_service import ConfluenceService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "confluence")

        if not connection:
            return ToolResult(output="Confluence is not connected.", sources=[])

        page = await ConfluenceService.get_page_content(
            db=db, connection=connection, page_id=page_id
        )

        if not page:
            return ToolResult(
                output=f"Could not find Confluence page with ID {page_id}.",
                sources=[],
            )

        title = page.get("title", "Untitled")
        space = page.get("space_name") or page.get("space_key", "")
        content = page.get("content", "")
        url = page.get("url", "")

        # Truncate if too long
        if len(content) > 4000:
            content = content[:4000] + "\n\n... [content truncated]"

        lines = [
            f"# {title}\n",
            f"**Space:** {space}",
            f"**Version:** {page.get('version', 'Unknown')}\n",
            "---\n",
            content,
        ]

        if url:
            lines.append(f"\n[Open in Confluence]({url})")

        sources = []
        if url:
            sources.append({"type": "confluence_page", "name": title, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_confluence_page.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_confluence_pages_in_space(
    context: Dict[str, Any],
    space_key: str,
    max_results: int = 20,
) -> ToolResult:
    """List pages in a Confluence space."""
    from backend.integrations.confluence_client import ConfluenceClient
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "confluence")

        if not connection:
            return ToolResult(output="Confluence is not connected.", sources=[])

        config = connection.get("config", {})
        access_token = config.get("access_token")
        cloud_id = config.get("cloud_id")
        base_url = config.get("base_url")

        if not access_token:
            return ToolResult(output="Confluence access token not configured.", sources=[])

        async with ConfluenceClient(
            access_token=access_token,
            cloud_id=cloud_id,
            base_url=base_url,
        ) as client:
            pages = await client.get_pages_in_space(space_key, limit=max_results)

        if not pages:
            return ToolResult(
                output=f"No pages found in Confluence space '{space_key}'.",
                sources=[],
            )

        lines = [f"Found {len(pages)} page(s) in space '{space_key}':\n"]
        sources = []

        for page in pages:
            page_id = page.get("id", "")
            title = page.get("title", "Untitled")
            version = page.get("version", {}).get("number", "?")

            # Build URL
            page_url = ""
            if base_url:
                page_url = f"{base_url}/wiki/spaces/{space_key}/pages/{page_id}"

            lines.append(f"- **{title}** (v{version})")
            if page_url:
                lines.append(f"  - [Open Page]({page_url})")
            lines.append("")

            if page_url:
                sources.append({"type": "confluence_page", "name": title, "url": page_url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_confluence_pages_in_space.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


CONFLUENCE_TOOLS = {
    "confluence.search_pages": search_confluence_pages,
    "confluence.get_page": get_confluence_page,
    "confluence.list_pages_in_space": list_confluence_pages_in_space,
}
