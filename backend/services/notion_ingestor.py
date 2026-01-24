"""
Notion content ingestor for NAVI memory system.

Ingests Notion pages and databases into the memory graph
for semantic search and context retrieval.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone
import structlog

from sqlalchemy.orm import Session

from backend.integrations.notion_client import NotionClient
from backend.models.memory_graph import MemoryNode

logger = structlog.get_logger(__name__)


class NotionIngestor:
    """
    Ingests Notion content into NAVI memory system.

    Supports:
    - Page content ingestion (converted to markdown)
    - Database row ingestion
    - Hierarchical page structure
    - Incremental sync
    """

    def __init__(
        self,
        client: NotionClient,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.client = client
        self.org_id = org_id
        self.user_id = user_id
        logger.info("NotionIngestor initialized", org_id=org_id, user_id=user_id)

    async def ingest_page(
        self,
        page_id: str,
        db: Session,
        include_children: bool = True,
    ) -> Dict[str, Any]:
        """
        Ingest a single Notion page into memory.

        Args:
            page_id: Notion page ID
            db: Database session
            include_children: Whether to recursively ingest child pages

        Returns:
            Ingestion result with page info
        """
        try:
            # Get page metadata
            page = await self.client.get_page(page_id)
            title = self.client.extract_page_title(page)

            # Get page content as markdown
            content = await self.client.page_to_markdown(page_id)

            # Extract metadata
            page_url = page.get("url") or ""
            created_time = page.get("created_time") or ""
            last_edited_time = page.get("last_edited_time") or ""
            parent = page.get("parent") or {}
            parent_type = parent.get("type") or "unknown"

            # Create memory node
            node = MemoryNode(
                org_id=self.org_id,
                node_type="notion_page",
                title=title or "Untitled",
                text=content[:10000] if content else "",  # Limit content size
                meta_json={
                    "page_id": page_id,
                    "url": page_url,
                    "parent_type": parent_type,
                    "created_time": created_time,
                    "last_edited_time": last_edited_time,
                    "user_id": self.user_id,
                    "content_length": len(content) if content else 0,
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(node)

            # Recursively ingest child pages if requested
            children_ingested = 0
            if include_children:
                blocks = await self.client.get_all_page_content(page_id)
                for block in blocks:
                    if block.get("type") == "child_page":
                        child_id = block.get("id")
                        if child_id:
                            await self.ingest_page(child_id, db, include_children=True)
                            children_ingested += 1

            db.commit()

            logger.info(
                "notion_ingestor.page_ingested",
                page_id=page_id,
                title=title,
                content_length=len(content) if content else 0,
                children=children_ingested,
            )

            return {
                "page_id": page_id,
                "title": title,
                "content_length": len(content) if content else 0,
                "children_ingested": children_ingested,
            }

        except Exception as exc:
            logger.error(
                "notion_ingestor.page_error",
                page_id=page_id,
                error=str(exc),
            )
            raise

    async def ingest_database(
        self,
        database_id: str,
        db: Session,
        filter_obj: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Ingest all rows from a Notion database.

        Args:
            database_id: Notion database ID
            db: Database session
            filter_obj: Optional Notion filter object
            limit: Maximum number of rows to ingest

        Returns:
            Ingestion result with row count
        """
        try:
            # Get database metadata
            database = await self.client.get_database(database_id)
            db_title = ""
            title_items = database.get("title") or []
            if title_items:
                db_title = self.client.extract_plain_text(title_items)

            # Query all rows
            rows = await self.client.query_all_database(
                database_id,
                filter_obj=filter_obj,
            )

            if limit:
                rows = rows[:limit]

            # Ingest each row
            rows_ingested = 0
            for row in rows:
                row_title = self.client.extract_page_title(row)
                row_id = row.get("id")
                row_url = row.get("url") or ""

                # Extract property values as text
                properties = row.get("properties") or {}
                prop_texts = []
                for prop_name, prop_value in properties.items():
                    prop_type = prop_value.get("type")
                    text = self._extract_property_text(prop_value, prop_type)
                    if text:
                        prop_texts.append(f"{prop_name}: {text}")

                content = "\n".join(prop_texts)

                node = MemoryNode(
                    org_id=self.org_id,
                    node_type="notion_database_row",
                    title=f"{db_title}: {row_title}" if row_title else db_title,
                    text=content[:5000] if content else "",
                    meta_json={
                        "database_id": database_id,
                        "database_title": db_title,
                        "row_id": row_id,
                        "url": row_url,
                        "user_id": self.user_id,
                    },
                    created_at=datetime.now(timezone.utc),
                )
                db.add(node)
                rows_ingested += 1

            db.commit()

            logger.info(
                "notion_ingestor.database_ingested",
                database_id=database_id,
                title=db_title,
                rows=rows_ingested,
            )

            return {
                "database_id": database_id,
                "title": db_title,
                "rows_ingested": rows_ingested,
            }

        except Exception as exc:
            logger.error(
                "notion_ingestor.database_error",
                database_id=database_id,
                error=str(exc),
            )
            raise

    async def ingest_workspace(
        self,
        db: Session,
        page_limit: int = 100,
        database_limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Ingest all accessible content from a Notion workspace.

        Args:
            db: Database session
            page_limit: Maximum number of pages to ingest
            database_limit: Maximum number of databases to ingest

        Returns:
            Ingestion summary
        """
        try:
            pages_ingested = 0
            databases_ingested = 0

            # Ingest pages
            search_results = await self.client.search(
                query="",
                filter_type="page",
                page_size=min(page_limit, 100),
            )
            pages = search_results.get("results") or []

            for page in pages[:page_limit]:
                page_id = page.get("id")
                if page_id:
                    try:
                        await self.ingest_page(page_id, db, include_children=False)
                        pages_ingested += 1
                    except Exception as exc:
                        logger.warning(
                            "notion_ingestor.page_skipped",
                            page_id=page_id,
                            error=str(exc),
                        )

            # Ingest databases
            db_results = await self.client.list_databases(
                page_size=min(database_limit, 100)
            )
            databases = db_results.get("results") or []

            for database in databases[:database_limit]:
                database_id = database.get("id")
                if database_id:
                    try:
                        await self.ingest_database(database_id, db, limit=50)
                        databases_ingested += 1
                    except Exception as exc:
                        logger.warning(
                            "notion_ingestor.database_skipped",
                            database_id=database_id,
                            error=str(exc),
                        )

            logger.info(
                "notion_ingestor.workspace_ingested",
                pages=pages_ingested,
                databases=databases_ingested,
            )

            return {
                "pages_ingested": pages_ingested,
                "databases_ingested": databases_ingested,
            }

        except Exception as exc:
            logger.error(
                "notion_ingestor.workspace_error",
                error=str(exc),
            )
            raise

    def _extract_property_text(
        self,
        prop_value: Dict[str, Any],
        prop_type: str,
    ) -> str:
        """Extract text from a Notion property value."""
        if prop_type == "title":
            return self.client.extract_plain_text(prop_value.get("title") or [])

        elif prop_type == "rich_text":
            return self.client.extract_plain_text(prop_value.get("rich_text") or [])

        elif prop_type == "number":
            value = prop_value.get("number")
            return str(value) if value is not None else ""

        elif prop_type == "select":
            select = prop_value.get("select") or {}
            return select.get("name") or ""

        elif prop_type == "multi_select":
            items = prop_value.get("multi_select") or []
            return ", ".join(item.get("name") or "" for item in items)

        elif prop_type == "status":
            status = prop_value.get("status") or {}
            return status.get("name") or ""

        elif prop_type == "date":
            date = prop_value.get("date") or {}
            start = date.get("start") or ""
            end = date.get("end") or ""
            return f"{start} - {end}" if end else start

        elif prop_type == "checkbox":
            return "Yes" if prop_value.get("checkbox") else "No"

        elif prop_type == "url":
            return prop_value.get("url") or ""

        elif prop_type == "email":
            return prop_value.get("email") or ""

        elif prop_type == "phone_number":
            return prop_value.get("phone_number") or ""

        elif prop_type == "people":
            people = prop_value.get("people") or []
            return ", ".join(p.get("name") or "" for p in people)

        elif prop_type == "relation":
            relations = prop_value.get("relation") or []
            return f"{len(relations)} related items"

        elif prop_type == "formula":
            formula = prop_value.get("formula") or {}
            formula_type = formula.get("type")
            if formula_type == "string":
                return formula.get("string") or ""
            elif formula_type == "number":
                value = formula.get("number")
                return str(value) if value is not None else ""
            elif formula_type == "boolean":
                return "Yes" if formula.get("boolean") else "No"
            elif formula_type == "date":
                date = formula.get("date") or {}
                return date.get("start") or ""
            return ""

        elif prop_type == "created_time":
            return prop_value.get("created_time") or ""

        elif prop_type == "last_edited_time":
            return prop_value.get("last_edited_time") or ""

        elif prop_type == "created_by":
            user = prop_value.get("created_by") or {}
            return user.get("name") or ""

        elif prop_type == "last_edited_by":
            user = prop_value.get("last_edited_by") or {}
            return user.get("name") or ""

        elif prop_type == "files":
            files = prop_value.get("files") or []
            return ", ".join(f.get("name") or "" for f in files)

        return ""


async def ingest_notion_for_user(
    access_token: str,
    org_id: Optional[str],
    user_id: Optional[str],
    db: Session,
    page_limit: int = 100,
    database_limit: int = 20,
) -> Dict[str, Any]:
    """
    Convenience function to ingest Notion workspace for a user.

    Args:
        access_token: Notion OAuth access token
        org_id: Organization ID
        user_id: User ID
        db: Database session
        page_limit: Max pages to ingest
        database_limit: Max databases to ingest

    Returns:
        Ingestion summary
    """
    async with NotionClient(access_token=access_token) as client:
        ingestor = NotionIngestor(
            client=client,
            org_id=org_id,
            user_id=user_id,
        )
        return await ingestor.ingest_workspace(
            db=db,
            page_limit=page_limit,
            database_limit=database_limit,
        )
