"""
Monday.com service for NAVI connector integration.

Provides syncing and querying of Monday.com boards, items, and updates.
"""

from typing import Any, Dict, List, Optional
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class MondayService(ConnectorServiceBase):
    """Service for Monday.com work management integration."""

    PROVIDER = "monday"
    SUPPORTED_ITEM_TYPES = ["board", "item", "update"]
    WRITE_OPERATIONS = ["create_item", "update_item", "create_update", "archive_item"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Monday.com boards and items to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (board, item)
            **kwargs: Additional args

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.monday_client import MondayClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            raise ValueError("Monday.com API token not configured")

        user_id = connection.get("user_id")
        types_to_sync = item_types or cls.SUPPORTED_ITEM_TYPES
        counts = {}

        async with MondayClient(api_token=api_token) as client:
            # Sync boards
            if "board" in types_to_sync:
                boards = await client.list_boards(limit=50)
                counts["board"] = 0

                for board in boards:
                    board_id = board.get("id", "")
                    name = board.get("name", "Untitled")

                    cls.upsert_item(
                        db=db,
                        user_id=user_id,
                        provider=cls.PROVIDER,
                        item_type="board",
                        external_id=board_id,
                        title=name,
                        url=f"https://monday.com/boards/{board_id}",
                        metadata={
                            "state": board.get("state"),
                            "board_kind": board.get("board_kind"),
                            "description": board.get("description"),
                        },
                    )
                    counts["board"] += 1

                logger.info(
                    "monday.sync_boards",
                    user_id=user_id,
                    count=counts["board"],
                )

            # Sync items from each board
            if "item" in types_to_sync:
                counts["item"] = 0
                boards = await client.list_boards(limit=20)

                for board in boards:
                    board_id = int(board.get("id", 0))
                    if not board_id:
                        continue

                    items_data = await client.get_items(board_id=board_id, limit=100)
                    items = items_data.get("items", [])

                    for item in items:
                        item_id = item.get("id", "")
                        name = item.get("name", "Untitled")

                        cls.upsert_item(
                            db=db,
                            user_id=user_id,
                            provider=cls.PROVIDER,
                            item_type="item",
                            external_id=item_id,
                            title=name,
                            url=f"https://monday.com/boards/{board_id}/pulses/{item_id}",
                            metadata={
                                "board_id": board_id,
                                "state": item.get("state"),
                                "group": item.get("group", {}).get("title"),
                                "created_at": item.get("created_at"),
                            },
                        )
                        counts["item"] += 1

                logger.info(
                    "monday.sync_items",
                    user_id=user_id,
                    count=counts["item"],
                )

        return counts

    @classmethod
    async def write_item(
        cls,
        db,
        connection: Dict[str, Any],
        operation: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform write operations on Monday.com.

        Supported operations:
        - create_item: Create a new item
        - update_item: Update an item
        - create_update: Add a comment to an item
        - archive_item: Archive an item

        Args:
            db: Database session
            connection: Connector connection dict
            operation: Operation name
            **kwargs: Operation-specific arguments

        Returns:
            Result dict with operation outcome
        """
        from backend.integrations.monday_client import MondayClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            raise ValueError("Monday.com API token not configured")

        async with MondayClient(api_token=api_token) as client:
            if operation == "create_item":
                board_id = kwargs.get("board_id")
                item_name = kwargs.get("item_name")
                group_id = kwargs.get("group_id")
                column_values = kwargs.get("column_values")

                if not board_id or not item_name:
                    raise ValueError("board_id and item_name are required")

                result = await client.create_item(
                    board_id=int(board_id),
                    item_name=item_name,
                    group_id=group_id,
                    column_values=column_values,
                )

                return {
                    "success": True,
                    "item_id": result.get("id"),
                    "name": result.get("name"),
                }

            elif operation == "create_update":
                item_id = kwargs.get("item_id")
                body = kwargs.get("body")

                if not item_id or not body:
                    raise ValueError("item_id and body are required")

                result = await client.create_update(
                    item_id=int(item_id),
                    body=body,
                )

                return {
                    "success": True,
                    "update_id": result.get("id"),
                }

            elif operation == "archive_item":
                item_id = kwargs.get("item_id")

                if not item_id:
                    raise ValueError("item_id is required")

                result = await client.archive_item(item_id=int(item_id))

                return {
                    "success": True,
                    "item_id": result.get("id"),
                    "state": result.get("state"),
                }

            else:
                raise ValueError(f"Unsupported operation: {operation}")

    @classmethod
    async def list_boards(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Monday.com boards.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of board dicts
        """
        from backend.integrations.monday_client import MondayClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with MondayClient(api_token=api_token) as client:
            boards = await client.list_boards(limit=max_results)

            return [
                {
                    "id": b.get("id", ""),
                    "name": b.get("name", "Untitled"),
                    "state": b.get("state", ""),
                    "board_kind": b.get("board_kind", ""),
                    "description": b.get("description", ""),
                    "url": f"https://monday.com/boards/{b.get('id', '')}",
                }
                for b in boards
            ]

    @classmethod
    async def list_items(
        cls,
        db,
        connection: Dict[str, Any],
        board_id: int,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List items in a Monday.com board.

        Args:
            db: Database session
            connection: Connector connection dict
            board_id: Board ID
            max_results: Maximum results to return

        Returns:
            List of item dicts
        """
        from backend.integrations.monday_client import MondayClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with MondayClient(api_token=api_token) as client:
            items_data = await client.get_items(board_id=board_id, limit=max_results)
            items = items_data.get("items", [])

            return [
                {
                    "id": i.get("id", ""),
                    "name": i.get("name", "Untitled"),
                    "state": i.get("state", ""),
                    "group": i.get("group", {}).get("title", ""),
                    "created_at": i.get("created_at", ""),
                    "updated_at": i.get("updated_at", ""),
                    "url": f"https://monday.com/boards/{board_id}/pulses/{i.get('id', '')}",
                    "column_values": [
                        {
                            "id": cv.get("id", ""),
                            "type": cv.get("type", ""),
                            "text": cv.get("text", ""),
                        }
                        for cv in i.get("column_values", [])
                    ],
                }
                for i in items
            ]

    @classmethod
    async def get_item(
        cls,
        db,
        connection: Dict[str, Any],
        item_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific Monday.com item.

        Args:
            db: Database session
            connection: Connector connection dict
            item_id: Item ID

        Returns:
            Item dict or None
        """
        from backend.integrations.monday_client import MondayClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return None

        async with MondayClient(api_token=api_token) as client:
            item = await client.get_item(item_id=item_id)

            if not item:
                return None

            board = item.get("board", {})
            board_id = board.get("id", "")

            return {
                "id": item.get("id", ""),
                "name": item.get("name", "Untitled"),
                "state": item.get("state", ""),
                "board_id": board_id,
                "board_name": board.get("name", ""),
                "group": item.get("group", {}).get("title", ""),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "url": f"https://monday.com/boards/{board_id}/pulses/{item.get('id', '')}",
                "column_values": [
                    {
                        "id": cv.get("id", ""),
                        "type": cv.get("type", ""),
                        "text": cv.get("text", ""),
                    }
                    for cv in item.get("column_values", [])
                ],
                "updates": [
                    {
                        "id": u.get("id", ""),
                        "body": u.get("body", ""),
                        "created_at": u.get("created_at", ""),
                        "creator": u.get("creator", {}).get("name", ""),
                    }
                    for u in item.get("updates", [])
                ],
            }

    @classmethod
    async def get_my_items(
        cls,
        db,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get items assigned to the current user.

        Args:
            db: Database session
            connection: Connector connection dict
            max_results: Maximum results to return

        Returns:
            List of items assigned to the user
        """
        from backend.integrations.monday_client import MondayClient

        config = connection.get("config", {})
        api_token = config.get("access_token") or config.get("api_token")

        if not api_token:
            return []

        async with MondayClient(api_token=api_token) as client:
            # Get current user
            me = await client.get_me()
            user_id = me.get("id")

            if not user_id:
                return []

            # Get all boards and filter items assigned to user
            boards = await client.list_boards(limit=20)
            my_items = []

            for board in boards:
                board_id = int(board.get("id", 0))
                if not board_id:
                    continue

                items_data = await client.get_items(board_id=board_id, limit=50)
                items = items_data.get("items", [])

                for item in items:
                    # Check if user is assigned (check people column)
                    for cv in item.get("column_values", []):
                        if cv.get("type") == "people":
                            value = cv.get("value")
                            if value and str(user_id) in str(value):
                                my_items.append(
                                    {
                                        "id": item.get("id", ""),
                                        "name": item.get("name", "Untitled"),
                                        "board_name": board.get("name", ""),
                                        "board_id": board_id,
                                        "group": item.get("group", {}).get("title", ""),
                                        "url": f"https://monday.com/boards/{board_id}/pulses/{item.get('id', '')}",
                                    }
                                )
                                break

                    if len(my_items) >= max_results:
                        break

                if len(my_items) >= max_results:
                    break

            return my_items
