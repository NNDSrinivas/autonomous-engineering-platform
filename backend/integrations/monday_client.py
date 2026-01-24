"""
Monday.com API client for work management.

Provides access to Monday.com boards, items, and updates via GraphQL.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class MondayClient:
    """
    Async Monday.com API client using GraphQL.

    Supports:
    - Board management
    - Item (task) operations
    - Column values
    - Updates (comments)
    - Webhooks
    """

    BASE_URL = "https://api.monday.com/v2"

    def __init__(
        self,
        api_token: str,
        timeout: float = 30.0,
    ):
        self.api_token = api_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "MondayClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": self.api_token,
                "Content-Type": "application/json",
                "API-Version": "2024-01",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    async def _query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        resp = await self.client.post("", json=payload)
        resp.raise_for_status()
        result = resp.json()

        if result.get("errors"):
            error_msg = result["errors"][0].get("message", "Unknown error")
            raise Exception(f"Monday.com API error: {error_msg}")

        return result.get("data", {})

    # -------------------------------------------------------------------------
    # User
    # -------------------------------------------------------------------------

    async def get_me(self) -> Dict[str, Any]:
        """Get the authenticated user."""
        query = """
        query {
            me {
                id
                name
                email
                account {
                    id
                    name
                }
            }
        }
        """
        data = await self._query(query)
        return data.get("me", {})

    async def get_users(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get users in the account."""
        query = """
        query ($limit: Int) {
            users (limit: $limit) {
                id
                name
                email
                enabled
                is_admin
            }
        }
        """
        data = await self._query(query, {"limit": limit})
        return data.get("users", [])

    # -------------------------------------------------------------------------
    # Boards
    # -------------------------------------------------------------------------

    async def list_boards(
        self,
        limit: int = 50,
        page: int = 1,
        board_kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List boards.

        Args:
            limit: Results per page
            page: Page number
            board_kind: Filter by type (public, private, share)

        Returns:
            List of boards
        """
        query = """
        query ($limit: Int, $page: Int, $boardKind: BoardKind) {
            boards (limit: $limit, page: $page, board_kind: $boardKind) {
                id
                name
                description
                state
                board_kind
                owner {
                    id
                    name
                }
                columns {
                    id
                    title
                    type
                }
            }
        }
        """
        variables: Dict[str, Any] = {"limit": limit, "page": page}
        if board_kind:
            variables["boardKind"] = board_kind

        data = await self._query(query, variables)
        return data.get("boards", [])

    async def get_board(
        self,
        board_id: int,
    ) -> Dict[str, Any]:
        """Get a specific board with items."""
        query = """
        query ($boardId: [ID!]) {
            boards (ids: $boardId) {
                id
                name
                description
                state
                board_kind
                owner {
                    id
                    name
                }
                columns {
                    id
                    title
                    type
                    settings_str
                }
                groups {
                    id
                    title
                    color
                }
                items_page (limit: 100) {
                    items {
                        id
                        name
                        state
                        group {
                            id
                            title
                        }
                    }
                }
            }
        }
        """
        data = await self._query(query, {"boardId": [str(board_id)]})
        boards = data.get("boards", [])
        return boards[0] if boards else {}

    async def create_board(
        self,
        name: str,
        board_kind: str = "public",
        folder_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new board."""
        query = """
        mutation ($name: String!, $boardKind: BoardKind!, $folderId: ID, $workspaceId: ID) {
            create_board (board_name: $name, board_kind: $boardKind, folder_id: $folderId, workspace_id: $workspaceId) {
                id
                name
            }
        }
        """
        variables: Dict[str, Any] = {"name": name, "boardKind": board_kind}
        if folder_id:
            variables["folderId"] = folder_id
        if workspace_id:
            variables["workspaceId"] = workspace_id

        data = await self._query(query, variables)
        return data.get("create_board", {})

    async def archive_board(
        self,
        board_id: int,
    ) -> Dict[str, Any]:
        """Archive a board."""
        query = """
        mutation ($boardId: ID!) {
            archive_board (board_id: $boardId) {
                id
                state
            }
        }
        """
        data = await self._query(query, {"boardId": board_id})
        return data.get("archive_board", {})

    # -------------------------------------------------------------------------
    # Items
    # -------------------------------------------------------------------------

    async def get_items(
        self,
        board_id: int,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get items from a board with pagination."""
        query = """
        query ($boardId: [ID!], $limit: Int, $cursor: String) {
            boards (ids: $boardId) {
                items_page (limit: $limit, cursor: $cursor) {
                    cursor
                    items {
                        id
                        name
                        state
                        created_at
                        updated_at
                        group {
                            id
                            title
                        }
                        column_values {
                            id
                            type
                            text
                            value
                        }
                    }
                }
            }
        }
        """
        variables: Dict[str, Any] = {"boardId": [str(board_id)], "limit": limit}
        if cursor:
            variables["cursor"] = cursor

        data = await self._query(query, variables)
        boards = data.get("boards", [])
        return boards[0].get("items_page", {}) if boards else {}

    async def get_item(
        self,
        item_id: int,
    ) -> Dict[str, Any]:
        """Get a specific item."""
        query = """
        query ($itemId: [ID!]) {
            items (ids: $itemId) {
                id
                name
                state
                created_at
                updated_at
                board {
                    id
                    name
                }
                group {
                    id
                    title
                }
                column_values {
                    id
                    type
                    text
                    value
                }
                updates {
                    id
                    body
                    created_at
                    creator {
                        name
                    }
                }
            }
        }
        """
        data = await self._query(query, {"itemId": [str(item_id)]})
        items = data.get("items", [])
        return items[0] if items else {}

    async def create_item(
        self,
        board_id: int,
        item_name: str,
        group_id: Optional[str] = None,
        column_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an item.

        Args:
            board_id: Board ID
            item_name: Item name
            group_id: Group to add item to
            column_values: Column values as JSON string

        Returns:
            Created item
        """
        import json

        query = """
        mutation ($boardId: ID!, $itemName: String!, $groupId: String, $columnValues: JSON) {
            create_item (board_id: $boardId, item_name: $itemName, group_id: $groupId, column_values: $columnValues) {
                id
                name
            }
        }
        """
        variables: Dict[str, Any] = {"boardId": board_id, "itemName": item_name}
        if group_id:
            variables["groupId"] = group_id
        if column_values:
            variables["columnValues"] = json.dumps(column_values)

        data = await self._query(query, variables)
        return data.get("create_item", {})

    async def update_item_name(
        self,
        board_id: int,
        item_id: int,
        name: str,
    ) -> Dict[str, Any]:
        """Update an item's name."""
        query = """
        mutation ($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
            change_multiple_column_values (board_id: $boardId, item_id: $itemId, column_values: $columnValues) {
                id
                name
            }
        }
        """
        import json

        data = await self._query(
            query,
            {
                "boardId": board_id,
                "itemId": item_id,
                "columnValues": json.dumps({"name": name}),
            },
        )
        return data.get("change_multiple_column_values", {})

    async def update_column_value(
        self,
        board_id: int,
        item_id: int,
        column_id: str,
        value: str,
    ) -> Dict[str, Any]:
        """Update a column value on an item."""
        query = """
        mutation ($boardId: ID!, $itemId: ID!, $columnId: String!, $value: JSON!) {
            change_column_value (board_id: $boardId, item_id: $itemId, column_id: $columnId, value: $value) {
                id
                name
            }
        }
        """
        data = await self._query(
            query,
            {
                "boardId": board_id,
                "itemId": item_id,
                "columnId": column_id,
                "value": value,
            },
        )
        return data.get("change_column_value", {})

    async def move_item_to_group(
        self,
        item_id: int,
        group_id: str,
    ) -> Dict[str, Any]:
        """Move an item to a different group."""
        query = """
        mutation ($itemId: ID!, $groupId: String!) {
            move_item_to_group (item_id: $itemId, group_id: $groupId) {
                id
            }
        }
        """
        data = await self._query(query, {"itemId": item_id, "groupId": group_id})
        return data.get("move_item_to_group", {})

    async def archive_item(
        self,
        item_id: int,
    ) -> Dict[str, Any]:
        """Archive an item."""
        query = """
        mutation ($itemId: ID!) {
            archive_item (item_id: $itemId) {
                id
                state
            }
        }
        """
        data = await self._query(query, {"itemId": item_id})
        return data.get("archive_item", {})

    async def delete_item(
        self,
        item_id: int,
    ) -> Dict[str, Any]:
        """Delete an item."""
        query = """
        mutation ($itemId: ID!) {
            delete_item (item_id: $itemId) {
                id
            }
        }
        """
        data = await self._query(query, {"itemId": item_id})
        return data.get("delete_item", {})

    # -------------------------------------------------------------------------
    # Groups
    # -------------------------------------------------------------------------

    async def create_group(
        self,
        board_id: int,
        group_name: str,
    ) -> Dict[str, Any]:
        """Create a group on a board."""
        query = """
        mutation ($boardId: ID!, $groupName: String!) {
            create_group (board_id: $boardId, group_name: $groupName) {
                id
                title
            }
        }
        """
        data = await self._query(query, {"boardId": board_id, "groupName": group_name})
        return data.get("create_group", {})

    async def archive_group(
        self,
        board_id: int,
        group_id: str,
    ) -> Dict[str, Any]:
        """Archive a group."""
        query = """
        mutation ($boardId: ID!, $groupId: String!) {
            archive_group (board_id: $boardId, group_id: $groupId) {
                id
            }
        }
        """
        data = await self._query(query, {"boardId": board_id, "groupId": group_id})
        return data.get("archive_group", {})

    # -------------------------------------------------------------------------
    # Updates (Comments)
    # -------------------------------------------------------------------------

    async def get_updates(
        self,
        item_id: int,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Get updates (comments) for an item."""
        query = """
        query ($itemId: [ID!], $limit: Int) {
            items (ids: $itemId) {
                updates (limit: $limit) {
                    id
                    body
                    text_body
                    created_at
                    creator {
                        id
                        name
                    }
                    replies {
                        id
                        body
                        creator {
                            name
                        }
                    }
                }
            }
        }
        """
        data = await self._query(query, {"itemId": [str(item_id)], "limit": limit})
        items = data.get("items", [])
        return items[0].get("updates", []) if items else []

    async def create_update(
        self,
        item_id: int,
        body: str,
    ) -> Dict[str, Any]:
        """Create an update (comment) on an item."""
        query = """
        mutation ($itemId: ID!, $body: String!) {
            create_update (item_id: $itemId, body: $body) {
                id
                body
                created_at
            }
        }
        """
        data = await self._query(query, {"itemId": item_id, "body": body})
        return data.get("create_update", {})

    # -------------------------------------------------------------------------
    # Workspaces
    # -------------------------------------------------------------------------

    async def list_workspaces(self) -> List[Dict[str, Any]]:
        """List workspaces."""
        query = """
        query {
            workspaces {
                id
                name
                kind
                description
            }
        }
        """
        data = await self._query(query)
        return data.get("workspaces", [])

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
        board_id: int,
    ) -> List[Dict[str, Any]]:
        """List webhooks for a board."""
        query = """
        query ($boardId: ID!) {
            webhooks (board_id: $boardId) {
                id
                board_id
                event
                config
            }
        }
        """
        data = await self._query(query, {"boardId": board_id})
        return data.get("webhooks", [])

    async def create_webhook(
        self,
        board_id: int,
        url: str,
        event: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            board_id: Board ID to watch
            url: Webhook URL
            event: Event type (change_column_value, create_item, etc.)
            config: Additional configuration

        Returns:
            Created webhook
        """
        import json

        query = """
        mutation ($boardId: ID!, $url: String!, $event: WebhookEventType!, $config: JSON) {
            create_webhook (board_id: $boardId, url: $url, event: $event, config: $config) {
                id
                board_id
            }
        }
        """
        variables: Dict[str, Any] = {
            "boardId": board_id,
            "url": url,
            "event": event,
        }
        if config:
            variables["config"] = json.dumps(config)

        data = await self._query(query, variables)
        return data.get("create_webhook", {})

    async def delete_webhook(
        self,
        webhook_id: int,
    ) -> Dict[str, Any]:
        """Delete a webhook."""
        query = """
        mutation ($webhookId: ID!) {
            delete_webhook (id: $webhookId) {
                id
            }
        }
        """
        data = await self._query(query, {"webhookId": webhook_id})
        return data.get("delete_webhook", {})
