"""Notion API client for AEP connector integration.

Notion uses a REST API with special handling for rich content.

Supports:
- Pages (list, get, create)
- Databases (list, query)
- Blocks (content extraction)
- Search
- User info
"""

from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


class NotionClient:
    """
    Notion API client for AEP NAVI integration.

    Note: Notion OAuth tokens don't expire, so no refresh token handling needed.
    """

    API_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("NotionClient initialized")

    async def __aenter__(self) -> "NotionClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Notion-Version": self.API_VERSION,
        }

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a GET request to the Notion API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.API_URL}{endpoint}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a POST request to the Notion API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.API_URL}{endpoint}"
        response = await self._client.post(url, json=data or {})
        response.raise_for_status()
        return response.json()

    async def _patch(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a PATCH request to the Notion API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.API_URL}{endpoint}"
        response = await self._client.patch(url, json=data or {})
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # User/Bot Methods
    # -------------------------------------------------------------------------

    async def get_me(self) -> Dict[str, Any]:
        """
        Get the bot user associated with this token.

        Returns:
            Bot user information
        """
        bot = await self._get("/users/me")
        logger.info("Notion bot fetched", name=bot.get("name"))
        return bot

    async def list_users(self, page_size: int = 100) -> List[Dict[str, Any]]:
        """
        List all users in the workspace.

        Args:
            page_size: Number of results per page

        Returns:
            List of user dictionaries
        """
        params = {"page_size": page_size}
        data = await self._get("/users", params=params)
        users = data.get("results", [])
        logger.info("Notion users listed", count=len(users))
        return users

    # -------------------------------------------------------------------------
    # Search Methods
    # -------------------------------------------------------------------------

    async def search(
        self,
        query: str,
        filter_type: Optional[str] = None,
        page_size: int = 50,
        start_cursor: Optional[str] = None,
        sort_direction: str = "descending",
        sort_timestamp: str = "last_edited_time",
    ) -> Dict[str, Any]:
        """
        Search for pages and databases.

        Args:
            query: Search query
            filter_type: Filter by object type ("page" or "database")
            page_size: Number of results per page
            start_cursor: Cursor for pagination
            sort_direction: Sort direction ("ascending" or "descending")
            sort_timestamp: Sort by timestamp ("last_edited_time")

        Returns:
            Search results with pagination info
        """
        payload: Dict[str, Any] = {
            "query": query,
            "page_size": page_size,
            "sort": {
                "direction": sort_direction,
                "timestamp": sort_timestamp,
            },
        }
        if filter_type:
            payload["filter"] = {"property": "object", "value": filter_type}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        data = await self._post("/search", payload)
        results = data.get("results", [])
        logger.info("Notion search completed", query=query, count=len(results))
        return data

    # -------------------------------------------------------------------------
    # Page Methods
    # -------------------------------------------------------------------------

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get a page by ID.

        Args:
            page_id: Page ID (with or without hyphens)

        Returns:
            Page metadata (not content - use get_page_content for blocks)
        """
        return await self._get(f"/pages/{page_id}")

    async def get_page_content(
        self,
        page_id: str,
        page_size: int = 100,
        start_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get page content (blocks).

        Args:
            page_id: Page ID
            page_size: Number of blocks per page
            start_cursor: Cursor for pagination

        Returns:
            Block children with pagination info
        """
        params: Dict[str, Any] = {"page_size": page_size}
        if start_cursor:
            params["start_cursor"] = start_cursor

        data = await self._get(f"/blocks/{page_id}/children", params=params)
        blocks = data.get("results", [])
        logger.info("Notion page content fetched", page_id=page_id, blocks=len(blocks))
        return data

    async def get_all_page_content(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Get all page content (handles pagination).

        Args:
            page_id: Page ID

        Returns:
            List of all blocks
        """
        all_blocks: List[Dict[str, Any]] = []
        start_cursor: Optional[str] = None

        while True:
            data = await self.get_page_content(page_id, start_cursor=start_cursor)
            all_blocks.extend(data.get("results", []))

            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")

        return all_blocks

    async def create_page(
        self,
        parent_id: str,
        parent_type: str,
        title: str,
        properties: Optional[Dict[str, Any]] = None,
        children: Optional[List[Dict[str, Any]]] = None,
        icon: Optional[Dict[str, Any]] = None,
        cover: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new page.

        Args:
            parent_id: Parent page or database ID
            parent_type: "page_id" or "database_id"
            title: Page title
            properties: Page properties (for database pages)
            children: Initial block content
            icon: Page icon (emoji or external URL)
            cover: Page cover image

        Returns:
            Created page
        """
        payload: Dict[str, Any] = {
            "parent": {parent_type: parent_id},
        }

        # Title handling depends on parent type
        if parent_type == "database_id":
            # Database page - title is a property
            if properties is None:
                properties = {}
            if "title" not in properties and "Name" not in properties:
                properties["Name"] = {"title": [{"text": {"content": title}}]}
            payload["properties"] = properties
        else:
            # Regular page - title is in properties
            payload["properties"] = {"title": [{"text": {"content": title}}]}

        if children:
            payload["children"] = children
        if icon:
            payload["icon"] = icon
        if cover:
            payload["cover"] = cover

        page = await self._post("/pages", payload)
        logger.info("Notion page created", page_id=page.get("id"))
        return page

    # -------------------------------------------------------------------------
    # Database Methods
    # -------------------------------------------------------------------------

    async def list_databases(
        self,
        page_size: int = 100,
        start_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all databases the integration has access to.

        Args:
            page_size: Number of results per page
            start_cursor: Cursor for pagination

        Returns:
            Search results filtered to databases
        """
        return await self.search(
            query="",
            filter_type="database",
            page_size=page_size,
            start_cursor=start_cursor,
        )

    async def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Get a database by ID.

        Args:
            database_id: Database ID

        Returns:
            Database metadata and schema
        """
        return await self._get(f"/databases/{database_id}")

    async def query_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        page_size: int = 100,
        start_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query a database with filters and sorts.

        Args:
            database_id: Database ID
            filter_obj: Notion filter object
            sorts: List of sort objects
            page_size: Number of results per page
            start_cursor: Cursor for pagination

        Returns:
            Query results with pagination info
        """
        payload: Dict[str, Any] = {"page_size": page_size}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor

        data = await self._post(f"/databases/{database_id}/query", payload)
        results = data.get("results", [])
        logger.info(
            "Notion database queried", database_id=database_id, count=len(results)
        )
        return data

    async def query_all_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query all rows from a database (handles pagination).

        Args:
            database_id: Database ID
            filter_obj: Notion filter object
            sorts: List of sort objects

        Returns:
            List of all database rows
        """
        all_results: List[Dict[str, Any]] = []
        start_cursor: Optional[str] = None

        while True:
            data = await self.query_database(
                database_id,
                filter_obj=filter_obj,
                sorts=sorts,
                start_cursor=start_cursor,
            )
            all_results.extend(data.get("results", []))

            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")

        return all_results

    # -------------------------------------------------------------------------
    # Block Methods
    # -------------------------------------------------------------------------

    async def get_block(self, block_id: str) -> Dict[str, Any]:
        """
        Get a block by ID.

        Args:
            block_id: Block ID

        Returns:
            Block details
        """
        return await self._get(f"/blocks/{block_id}")

    async def get_block_children(
        self,
        block_id: str,
        page_size: int = 100,
        start_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get children of a block.

        Args:
            block_id: Block ID
            page_size: Number of results per page
            start_cursor: Cursor for pagination

        Returns:
            Block children with pagination info
        """
        params: Dict[str, Any] = {"page_size": page_size}
        if start_cursor:
            params["start_cursor"] = start_cursor

        return await self._get(f"/blocks/{block_id}/children", params=params)

    async def append_block_children(
        self,
        block_id: str,
        children: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Append children to a block.

        Args:
            block_id: Block ID
            children: List of block objects to append

        Returns:
            Appended blocks
        """
        return await self._patch(
            f"/blocks/{block_id}/children",
            {"children": children},
        )

    # -------------------------------------------------------------------------
    # Content Extraction Helpers
    # -------------------------------------------------------------------------

    def extract_plain_text(self, rich_text: List[Dict[str, Any]]) -> str:
        """
        Extract plain text from Notion rich text array.

        Args:
            rich_text: Notion rich text array

        Returns:
            Plain text string
        """
        return "".join(item.get("plain_text", "") for item in rich_text)

    def extract_page_title(self, page: Dict[str, Any]) -> str:
        """
        Extract title from a page object.

        Args:
            page: Notion page object

        Returns:
            Page title string
        """
        properties = page.get("properties", {})

        # Try common title property names
        for prop_name in ["title", "Title", "Name", "name"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title":
                    return self.extract_plain_text(prop.get("title", []))

        # Fallback: find any title property
        for prop in properties.values():
            if prop.get("type") == "title":
                return self.extract_plain_text(prop.get("title", []))

        return ""

    def block_to_text(self, block: Dict[str, Any]) -> str:
        """
        Convert a block to plain text.

        Args:
            block: Notion block object

        Returns:
            Plain text representation
        """
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        # Text blocks
        if block_type in (
            "paragraph",
            "heading_1",
            "heading_2",
            "heading_3",
            "bulleted_list_item",
            "numbered_list_item",
            "toggle",
            "quote",
            "callout",
        ):
            rich_text = block_data.get("rich_text", [])
            text = self.extract_plain_text(rich_text)

            # Add formatting for headers
            if block_type == "heading_1":
                return f"# {text}"
            elif block_type == "heading_2":
                return f"## {text}"
            elif block_type == "heading_3":
                return f"### {text}"
            elif block_type == "bulleted_list_item":
                return f"• {text}"
            elif block_type == "numbered_list_item":
                return f"- {text}"
            elif block_type == "quote":
                return f"> {text}"
            elif block_type == "callout":
                icon = block_data.get("icon", {}).get("emoji", "")
                return f"{icon} {text}"

            return text

        # Code block
        if block_type == "code":
            rich_text = block_data.get("rich_text", [])
            language = block_data.get("language", "")
            code = self.extract_plain_text(rich_text)
            return f"```{language}\n{code}\n```"

        # To-do
        if block_type == "to_do":
            rich_text = block_data.get("rich_text", [])
            checked = block_data.get("checked", False)
            text = self.extract_plain_text(rich_text)
            checkbox = "[x]" if checked else "[ ]"
            return f"{checkbox} {text}"

        # Divider
        if block_type == "divider":
            return "---"

        # Bookmark / embed
        if block_type in ("bookmark", "embed"):
            url = block_data.get("url", "")
            return f"[{url}]({url})"

        # Image / file / video
        if block_type in ("image", "file", "video", "pdf"):
            file_data = block_data.get("file", {}) or block_data.get("external", {})
            url = file_data.get("url", "")
            return f"[{block_type}: {url}]"

        # Equation
        if block_type == "equation":
            expression = block_data.get("expression", "")
            return f"$${expression}$$"

        # Table row
        if block_type == "table_row":
            cells = block_data.get("cells", [])
            cell_texts = [self.extract_plain_text(cell) for cell in cells]
            return " | ".join(cell_texts)

        return ""

    async def page_to_markdown(self, page_id: str) -> str:
        """
        Convert a full page to markdown.

        Args:
            page_id: Page ID

        Returns:
            Markdown string
        """
        blocks = await self.get_all_page_content(page_id)
        lines = []

        for block in blocks:
            text = self.block_to_text(block)
            if text:
                lines.append(text)

        return "\n\n".join(lines)
