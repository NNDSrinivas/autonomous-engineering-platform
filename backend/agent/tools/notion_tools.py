"""
Notion tools for NAVI agent.

Provides tools for searching and reading Notion pages and databases.
Returns ToolResult with sources for clickable links in VS Code extension.
"""

from typing import Any, Dict, Optional
import logging
import structlog

from backend.services.connector_base import ToolResult

logger = logging.getLogger(__name__)
notion_logger = structlog.get_logger(__name__)


async def search_notion_pages(
    context: Dict[str, Any],
    query: str,
    max_results: int = 20,
) -> "ToolResult":
    """
    Search Notion pages by keyword.

    Args:
        context: NAVI context with user info
        query: Search query
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.notion_service import NotionService
    from backend.core.db import get_db

    notion_logger.info(
        "notion_tools.search_pages.start",
        query=query,
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Search pages
        items = NotionService.search_pages(
            db=db,
            user_id=user_id,
            query=query,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Untitled",
                "type": "notion",
                "connector": "notion",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Notion pages matching '{query}':\n\n"

            for item in items:
                icon = ""
                if item.data.get("icon"):
                    icon_data = item.data["icon"]
                    if icon_data.get("type") == "emoji":
                        icon = icon_data.get("emoji", "") + " "

                output += f"• {icon}**{item.title or 'Untitled'}**\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = f"No Notion pages found matching '{query}'."

        notion_logger.info(
            "notion_tools.search_pages.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        notion_logger.error("notion_tools.search_pages.error", error=str(exc))
        return ToolResult(
            output=f"Error searching Notion pages: {str(exc)}", sources=[]
        )


async def list_recent_notion_pages(
    context: Dict[str, Any],
    max_results: int = 20,
) -> "ToolResult":
    """
    List recently updated Notion pages.

    Args:
        context: NAVI context with user info
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.notion_service import NotionService
    from backend.core.db import get_db

    notion_logger.info(
        "notion_tools.list_recent_pages.start",
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Get recent pages
        items = NotionService.list_recent_pages(
            db=db,
            user_id=user_id,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Untitled",
                "type": "notion",
                "connector": "notion",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} recent Notion pages:\n\n"

            for item in items:
                icon = ""
                if item.data.get("icon"):
                    icon_data = item.data["icon"]
                    if icon_data.get("type") == "emoji":
                        icon = icon_data.get("emoji", "") + " "

                output += f"• {icon}**{item.title or 'Untitled'}**\n"
                if item.external_updated_at:
                    output += f"  Updated: {item.external_updated_at.strftime('%Y-%m-%d %H:%M')}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No Notion pages found. Make sure you have connected Notion."

        notion_logger.info(
            "notion_tools.list_recent_pages.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        notion_logger.error("notion_tools.list_recent_pages.error", error=str(exc))
        return ToolResult(output=f"Error listing Notion pages: {str(exc)}", sources=[])


async def get_notion_page_content(
    context: Dict[str, Any],
    page_id: str,
) -> "ToolResult":
    """
    Get the content of a Notion page.

    Args:
        context: NAVI context with user info
        page_id: Notion page ID

    Returns:
        ToolResult with page content in markdown
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.notion_service import NotionService
    from backend.core.db import get_db

    notion_logger.info(
        "notion_tools.get_page_content.start",
        page_id=page_id,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        # Get page content
        content = await NotionService.get_page_content(
            db=db,
            user_id=user_id,
            page_id=page_id,
            org_id=org_id,
        )

        if content:
            output = f"**Page Content:**\n\n{content}"

            # Try to get page URL from database
            items = NotionService.get_items(
                db=db,
                user_id=user_id,
                item_type="page",
                limit=100,
            )
            page_item = next(
                (
                    i
                    for i in items
                    if i.external_id == page_id or page_id in str(i.external_id)
                ),
                None,
            )

            sources = []
            if page_item and page_item.url:
                sources.append(
                    {
                        "name": page_item.title or "Page",
                        "type": "notion",
                        "connector": "notion",
                        "url": page_item.url,
                    }
                )

            notion_logger.info(
                "notion_tools.get_page_content.done",
                content_length=len(content),
            )

            return ToolResult(output=output, sources=sources)
        else:
            return ToolResult(
                output=f"Could not retrieve content for Notion page {page_id}. Make sure you have access.",
                sources=[],
            )

    except Exception as exc:
        notion_logger.error("notion_tools.get_page_content.error", error=str(exc))
        return ToolResult(
            output=f"Error getting Notion page content: {str(exc)}", sources=[]
        )


async def list_notion_databases(
    context: Dict[str, Any],
    max_results: int = 20,
) -> "ToolResult":
    """
    List Notion databases.

    Args:
        context: NAVI context with user info
        max_results: Maximum number of results

    Returns:
        ToolResult with formatted output and clickable sources
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.notion_service import NotionService
    from backend.core.db import get_db

    notion_logger.info(
        "notion_tools.list_databases.start",
        max_results=max_results,
    )

    try:
        db = next(get_db())
        user_id = context.get("user_id")

        # Get databases
        items = NotionService.list_databases(
            db=db,
            user_id=user_id,
            limit=max_results,
        )

        # Build clickable sources
        sources = [
            {
                "name": item.title[:50] if item.title else "Untitled Database",
                "type": "notion",
                "connector": "notion",
                "url": item.url,
            }
            for item in items
            if item.url
        ]

        # Format output
        if items:
            output = f"Found {len(items)} Notion databases:\n\n"

            for item in items:
                icon = ""
                if item.data.get("icon"):
                    icon_data = item.data["icon"]
                    if icon_data.get("type") == "emoji":
                        icon = icon_data.get("emoji", "") + " "

                output += f"• {icon}**{item.title or 'Untitled Database'}**\n"
                if item.description:
                    output += f"  Description: {item.description[:100]}\n"
                if item.url:
                    output += f"  Link: {item.url}\n"
                output += "\n"
        else:
            output = "No Notion databases found. Make sure you have connected Notion."

        notion_logger.info(
            "notion_tools.list_databases.done",
            count=len(items),
        )

        return ToolResult(output=output, sources=sources)

    except Exception as exc:
        notion_logger.error("notion_tools.list_databases.error", error=str(exc))
        return ToolResult(
            output=f"Error listing Notion databases: {str(exc)}", sources=[]
        )


async def create_notion_page(
    context: Dict[str, Any],
    parent_id: str,
    title: str,
    content: Optional[str] = None,
    approve: bool = False,
) -> "ToolResult":
    """
    Create a new Notion page.

    REQUIRES APPROVAL: This is a write operation.

    Args:
        context: NAVI context with user info
        parent_id: Parent page or database ID
        title: Page title
        content: Optional initial content (markdown)
        approve: Must be True to execute

    Returns:
        ToolResult with created page details
    """
    from backend.agent.tool_executor import ToolResult
    from backend.services.notion_service import NotionService
    from backend.core.db import get_db

    notion_logger.info(
        "notion_tools.create_page.start",
        parent_id=parent_id,
        title=title,
        approve=approve,
    )

    # Check approval
    if not approve:
        return ToolResult(
            output=f"**Action requires approval**: Create Notion page\n\n"
            f"• Title: {title}\n"
            f"• Parent ID: {parent_id}\n"
            f"• Content: {content[:100] + '...' if content and len(content) > 100 else content or 'None'}\n\n"
            f"Set `approve=True` to execute this action.",
            sources=[],
        )

    try:
        db = next(get_db())
        user_id = context.get("user_id")
        org_id = context.get("org_id")

        # Convert markdown content to Notion blocks if provided
        children = None
        if content:
            # Simple conversion: split by paragraphs
            children = []
            for para in content.split("\n\n"):
                if para.strip():
                    children.append(
                        {
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": para.strip()}}
                                ]
                            },
                        }
                    )

        result = await NotionService.write_item(
            db=db,
            user_id=user_id,
            item_type="page",
            action="create_page",
            data={
                "parent_id": parent_id,
                "parent_type": "page_id",
                "title": title,
                "children": children,
            },
            org_id=org_id,
        )

        if result.success:
            sources = []
            if result.url:
                sources.append(
                    {
                        "name": title[:50],
                        "type": "notion",
                        "connector": "notion",
                        "url": result.url,
                    }
                )

            output = "Successfully created Notion page:\n\n"
            output += f"• **{title}**\n"
            if result.url:
                output += f"• Link: {result.url}\n"

            notion_logger.info(
                "notion_tools.create_page.done",
                page_id=result.item_id,
            )

            return ToolResult(output=output, sources=sources)
        else:
            return ToolResult(
                output=f"Failed to create Notion page: {result.error}",
                sources=[],
            )

    except Exception as exc:
        notion_logger.error("notion_tools.create_page.error", error=str(exc))
        return ToolResult(output=f"Error creating Notion page: {str(exc)}", sources=[])


# Tool function registry for NAVI
NOTION_TOOLS = {
    "notion_search_pages": search_notion_pages,
    "notion_list_recent_pages": list_recent_notion_pages,
    "notion_get_page_content": get_notion_page_content,
    "notion_list_databases": list_notion_databases,
    "notion_create_page": create_notion_page,
}
