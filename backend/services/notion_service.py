"""
Notion service for NAVI integration.

Provides sync, query, and write operations for Notion pages and databases.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    ConnectorItem,
    SyncResult,
    WriteResult,
)
from backend.integrations.notion_client import NotionClient

logger = structlog.get_logger(__name__)


class NotionService(ConnectorServiceBase):
    """
    Notion connector service for NAVI.

    Supports:
    - Pages (list, search, read content, create)
    - Databases (list, query)
    """

    PROVIDER = "notion"
    SUPPORTED_ITEM_TYPES = ["page", "database"]
    WRITE_OPERATIONS = ["create_page"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync pages and databases from Notion to database.

        Args:
            db: Database session
            connection: Connection with credentials
            item_types: Optional list of types to sync (default: all)

        Returns:
            SyncResult with sync statistics
        """
        logger.info(
            "notion_service.sync_items.start",
            connector_id=connection.get("id"),
            item_types=item_types,
        )

        try:
            # Get credentials
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for Notion connection"
                )

            access_token = credentials.get("access_token")
            if not access_token:
                return SyncResult(
                    success=False, error="No access token in Notion credentials"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            types_to_sync = item_types or ["page", "database"]

            async with NotionClient(access_token) as client:
                if "page" in types_to_sync:
                    # Fetch pages via search
                    search_result = await client.search(
                        query="", filter_type="page", page_size=100
                    )
                    pages = search_result.get("results", [])

                    for page in pages:
                        external_id = page.get("id")

                        # Extract title
                        title = client.extract_page_title(page)

                        # Parse dates
                        created_at = None
                        updated_at = None
                        if page.get("created_time"):
                            try:
                                created_at = datetime.fromisoformat(
                                    page["created_time"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass
                        if page.get("last_edited_time"):
                            try:
                                updated_at = datetime.fromisoformat(
                                    page["last_edited_time"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass

                        # Build data dict
                        data = {
                            "parent": page.get("parent"),
                            "icon": page.get("icon"),
                            "cover": page.get("cover"),
                            "archived": page.get("archived"),
                            "properties": page.get("properties"),
                        }

                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="page",
                            external_id=external_id,
                            title=title,
                            url=page.get("url"),
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                            external_created_at=created_at,
                            external_updated_at=updated_at,
                        )

                        if result:
                            items_synced += 1

                    logger.info(
                        "notion_service.sync_items.pages_synced",
                        count=len(pages),
                    )

                if "database" in types_to_sync:
                    # Fetch databases via search
                    search_result = await client.search(
                        query="", filter_type="database", page_size=100
                    )
                    databases = search_result.get("results", [])

                    for database in databases:
                        external_id = database.get("id")

                        # Extract title
                        title_array = database.get("title", [])
                        title = client.extract_plain_text(title_array)

                        # Parse dates
                        created_at = None
                        updated_at = None
                        if database.get("created_time"):
                            try:
                                created_at = datetime.fromisoformat(
                                    database["created_time"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass
                        if database.get("last_edited_time"):
                            try:
                                updated_at = datetime.fromisoformat(
                                    database["last_edited_time"].replace("Z", "+00:00")
                                )
                            except Exception:
                                pass

                        # Build data dict with schema info
                        data = {
                            "parent": database.get("parent"),
                            "icon": database.get("icon"),
                            "cover": database.get("cover"),
                            "archived": database.get("archived"),
                            "is_inline": database.get("is_inline"),
                            "properties": database.get("properties"),
                        }

                        # Extract description
                        desc_array = database.get("description", [])
                        description = client.extract_plain_text(desc_array)

                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="database",
                            external_id=external_id,
                            title=title,
                            description=description,
                            url=database.get("url"),
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                            external_created_at=created_at,
                            external_updated_at=updated_at,
                        )

                        if result:
                            items_synced += 1

                    logger.info(
                        "notion_service.sync_items.databases_synced",
                        count=len(databases),
                    )

            # Update connector sync status
            cls.update_sync_status(db, connector_id, "success")

            logger.info(
                "notion_service.sync_items.complete",
                items_synced=items_synced,
            )

            return SyncResult(
                success=True,
                items_synced=items_synced,
            )

        except Exception as e:
            logger.error("notion_service.sync_items.error", error=str(e))
            cls.update_sync_status(db, connection.get("id"), "error", str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        user_id: str,
        item_type: str,
        action: str,
        data: Dict[str, Any],
        org_id: Optional[str] = None,
    ) -> WriteResult:
        """
        Write operation to Notion (create page).

        Args:
            db: Database session
            user_id: User performing the action
            item_type: Type of item
            action: Action to perform
            data: Data for the operation
            org_id: Optional organization ID

        Returns:
            WriteResult with success status
        """
        logger.info(
            "notion_service.write_item.start",
            user_id=user_id,
            item_type=item_type,
            action=action,
        )

        try:
            # Get connection
            connection = cls.get_connection(db, user_id, org_id)
            if not connection:
                return WriteResult(
                    success=False, error="No Notion connection found for user"
                )

            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(success=False, error="No credentials found")

            access_token = credentials.get("access_token")
            if not access_token:
                return WriteResult(success=False, error="No access token")

            async with NotionClient(access_token) as client:
                if action == "create_page":
                    parent_id = data.get("parent_id")
                    parent_type = data.get("parent_type", "page_id")
                    title = data.get("title")

                    if not parent_id or not title:
                        return WriteResult(
                            success=False,
                            error="parent_id and title are required for create_page",
                        )

                    page = await client.create_page(
                        parent_id=parent_id,
                        parent_type=parent_type,
                        title=title,
                        children=data.get("children"),
                    )

                    logger.info(
                        "notion_service.write_item.page_created",
                        page_id=page.get("id"),
                    )

                    return WriteResult(
                        success=True,
                        item_id=page.get("id"),
                        external_id=page.get("id"),
                        url=page.get("url"),
                        data=page,
                    )
                else:
                    return WriteResult(
                        success=False, error=f"Unknown action: {action}"
                    )

        except Exception as e:
            logger.error("notion_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    def search_pages(
        cls,
        db: Session,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        Search Notion pages by query.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="page",
            search_query=query,
            limit=limit,
        )

    @classmethod
    def list_recent_pages(
        cls,
        db: Session,
        user_id: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List recently updated Notion pages.

        Args:
            db: Database session
            user_id: User ID
            limit: Max results

        Returns:
            List of ConnectorItem objects (sorted by last updated)
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="page",
            limit=limit,
        )

    @classmethod
    def list_databases(
        cls,
        db: Session,
        user_id: str,
        limit: int = 20,
    ) -> List[ConnectorItem]:
        """
        List Notion databases.

        Args:
            db: Database session
            user_id: User ID
            limit: Max results

        Returns:
            List of ConnectorItem objects
        """
        return cls.get_items(
            db=db,
            user_id=user_id,
            item_type="database",
            limit=limit,
        )

    @classmethod
    async def get_page_content(
        cls,
        db: Session,
        user_id: str,
        page_id: str,
        org_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the content of a Notion page as markdown.

        Args:
            db: Database session
            user_id: User ID
            page_id: Notion page ID
            org_id: Optional org ID

        Returns:
            Markdown content or None
        """
        try:
            connection = cls.get_connection(db, user_id, org_id)
            if not connection:
                return None

            credentials = cls.get_credentials(connection)
            if not credentials:
                return None

            access_token = credentials.get("access_token")
            if not access_token:
                return None

            async with NotionClient(access_token) as client:
                return await client.page_to_markdown(page_id)

        except Exception as e:
            logger.error("notion_service.get_page_content.error", error=str(e))
            return None
