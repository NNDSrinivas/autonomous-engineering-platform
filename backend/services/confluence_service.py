"""
Confluence service for NAVI connector integration.

Provides syncing and querying of Confluence pages and spaces.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class ConfluenceService(ConnectorServiceBase):
    """Service for Confluence wiki integration."""

    PROVIDER = "confluence"
    SUPPORTED_ITEM_TYPES = ["page", "space"]
    WRITE_OPERATIONS = []  # Read-only for now

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Confluence pages and spaces to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (page, space)
            **kwargs: Additional args (space_key for filtering)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.confluence_client import ConfluenceClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        cloud_id = config.get("cloud_id")
        base_url = config.get("base_url")

        if not access_token:
            raise ValueError("Confluence access token not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        client = ConfluenceClient(
            access_token=access_token,
            cloud_id=cloud_id,
            base_url=base_url,
        )

        try:
            # Get space key filter if provided
            space_key = kwargs.get("space_key")

            if "page" in types_to_sync and space_key:
                pages = await client.get_pages_in_space(space_key, limit=100)
                counts["page"] = 0

                for page in pages:
                    page_id = page.get("id", "")
                    title = page.get("title", "Untitled")
                    space_info = page.get("space", {})
                    body = page.get("body", {}).get("storage", {}).get("value", "")

                    # Build URL
                    page_url = ""
                    if base_url:
                        page_url = f"{base_url}/wiki/spaces/{space_info.get('key', '')}/pages/{page_id}"
                    elif cloud_id:
                        page_url = f"https://your-domain.atlassian.net/wiki/spaces/{space_info.get('key', '')}/pages/{page_id}"

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="page",
                        external_id=page_id,
                        title=title,
                        content=(
                            ConfluenceClient.html_to_text(body)[:2000] if body else ""
                        ),
                        url=page_url,
                        metadata={
                            "space_key": space_info.get("key"),
                            "space_name": space_info.get("name"),
                            "version": page.get("version", {}).get("number"),
                        },
                    )
                    counts["page"] += 1

                logger.info(
                    "confluence.sync_pages",
                    user_id=user_id,
                    space_key=space_key,
                    count=counts["page"],
                )
        finally:
            await client.close()

        return counts

    @classmethod
    async def write_item(
        cls,
        db,
        connection: Dict[str, Any],
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Write operations not yet supported for Confluence."""
        raise NotImplementedError("Confluence write operations not yet supported")

    @classmethod
    async def search_pages(
        cls,
        db,
        connection: Dict[str, Any],
        query: str,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search Confluence pages using CQL.

        Args:
            db: Database session
            connection: Connector connection dict
            query: Search query (will be wrapped in CQL)
            max_results: Maximum results to return

        Returns:
            List of matching pages
        """
        from backend.integrations.confluence_client import ConfluenceClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        cloud_id = config.get("cloud_id")
        base_url = config.get("base_url")

        if not access_token:
            return []

        client = ConfluenceClient(
            access_token=access_token,
            cloud_id=cloud_id,
            base_url=base_url,
        )

        try:
            # Build CQL query
            cql = f'type=page AND text~"{query}"'
            pages = await client.search_pages(cql=cql, limit=max_results)

            results = []
            for page in pages:
                page_id = page.get("id", "")
                space_info = page.get("space", {})

                # Build URL
                page_url = ""
                if base_url:
                    page_url = f"{base_url}/wiki/spaces/{space_info.get('key', '')}/pages/{page_id}"

                results.append(
                    {
                        "id": page_id,
                        "title": page.get("title", "Untitled"),
                        "space_key": space_info.get("key"),
                        "space_name": space_info.get("name"),
                        "url": page_url,
                        "excerpt": ConfluenceClient.html_to_text(
                            page.get("body", {}).get("storage", {}).get("value", "")
                        )[:200],
                    }
                )

            return results
        finally:
            await client.close()

    @classmethod
    async def get_page_content(
        cls,
        db,
        connection: Dict[str, Any],
        page_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get full content of a Confluence page.

        Args:
            db: Database session
            connection: Connector connection dict
            page_id: Confluence page ID

        Returns:
            Page dict with content or None
        """
        from backend.integrations.confluence_client import ConfluenceClient

        config = connection.get("config", {})
        access_token = config.get("access_token")
        cloud_id = config.get("cloud_id")
        base_url = config.get("base_url")

        if not access_token:
            return None

        client = ConfluenceClient(
            access_token=access_token,
            cloud_id=cloud_id,
            base_url=base_url,
        )

        try:
            page = await client.get_page(page_id)

            if not page:
                return None

            space_info = page.get("space", {})
            body_html = page.get("body", {}).get("storage", {}).get("value", "")

            # Build URL
            page_url = ""
            if base_url:
                page_url = f"{base_url}/wiki/spaces/{space_info.get('key', '')}/pages/{page_id}"

            return {
                "id": page_id,
                "title": page.get("title", "Untitled"),
                "space_key": space_info.get("key"),
                "space_name": space_info.get("name"),
                "content": ConfluenceClient.html_to_text(body_html),
                "html_content": body_html,
                "url": page_url,
                "version": page.get("version", {}).get("number"),
            }
        finally:
            await client.close()

    @classmethod
    async def list_spaces(
        cls,
        db,
        connection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        List available Confluence spaces.

        Note: This requires an additional API call not in the current client.
        For now, returns empty list - would need client enhancement.
        """
        # TODO: Add list_spaces to ConfluenceClient
        return []


# Legacy sync function for backwards compatibility
def search_pages(
    db,
    query: str,
    user_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search Confluence pages by query text (legacy sync function).
    For unified memory retriever compatibility.
    """
    try:
        from backend.integrations.confluence_client import ConfluenceClient
    except ImportError:
        return []

    try:
        client = ConfluenceClient()
    except Exception:
        return []

    # This is a sync wrapper - for new code, use the async methods above
    import asyncio

    async def _search():
        try:
            cql = f'type=page AND text~"{query}"'
            return await client.search_pages(cql=cql, limit=limit)
        except Exception:
            return []
        finally:
            await client.close()

    try:
        pages = asyncio.run(_search())
    except Exception:
        return []

    normalized = []
    for page in pages or []:
        normalized.append(
            {
                "id": str(page.get("id") or ""),
                "title": page.get("title") or "",
                "excerpt": ConfluenceClient.html_to_text(
                    page.get("body", {}).get("storage", {}).get("value", "")
                )[:200],
                "body": page.get("body", {}).get("storage", {}).get("value", ""),
                "url": page.get("_links", {}).get("webui"),
                "updated_at": page.get("version", {}).get("when"),
                "space": (
                    page.get("space", {}).get("key")
                    if isinstance(page.get("space"), dict)
                    else page.get("space")
                ),
                "labels": page.get("labels") or [],
            }
        )

    return normalized
