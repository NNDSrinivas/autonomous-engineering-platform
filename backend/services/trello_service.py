"""
Trello service for NAVI integration.

Provides sync, query, and write operations for Trello boards, lists, and cards.
"""

from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    SyncResult,
    WriteResult,
)
from backend.integrations.trello_client import TrelloClient

logger = structlog.get_logger(__name__)


class TrelloService(ConnectorServiceBase):
    """
    Trello connector service for NAVI.

    Supports:
    - Boards (list)
    - Lists (list)
    - Cards (list, create, update)
    """

    PROVIDER = "trello"
    SUPPORTED_ITEM_TYPES = ["board", "list", "card"]
    WRITE_OPERATIONS = ["create_card", "update_card", "move_card"]

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync boards and cards from Trello to database.
        """
        logger.info(
            "trello_service.sync_items.start",
            connector_id=connection.get("id"),
        )

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(
                    success=False, error="No credentials found for Trello connection"
                )

            api_key = credentials.get("api_key")
            api_token = credentials.get("api_token") or credentials.get("access_token")
            if not api_key or not api_token:
                return SyncResult(
                    success=False, error="Missing Trello API key or token"
                )

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            types_to_sync = item_types or ["board", "card"]

            async with TrelloClient(api_key, api_token) as client:
                if "board" in types_to_sync:
                    boards = await client.get_member_boards()

                    for board in boards:
                        external_id = board.get("id", "")

                        data = {
                            "shortLink": board.get("shortLink"),
                            "closed": board.get("closed"),
                            "prefs": board.get("prefs"),
                        }

                        result = cls.upsert_item(
                            db=db,
                            connector_id=connector_id,
                            item_type="board",
                            external_id=external_id,
                            title=board.get("name"),
                            description=board.get("desc"),
                            status="closed" if board.get("closed") else "open",
                            url=board.get("url"),
                            user_id=user_id,
                            org_id=org_id,
                            data=data,
                        )

                        items_synced += 1
                        if result == "created":
                            items_created += 1
                        else:
                            items_updated += 1

                if "card" in types_to_sync:
                    boards = await client.get_member_boards(filter="open")

                    for board in boards[:10]:  # Limit to 10 boards
                        board_id = board.get("id")
                        board_name = board.get("name")

                        try:
                            board_data = await client.get_board(
                                board_id, lists=True, cards="open"
                            )
                            cards = board_data.get("cards", [])

                            for card in cards:
                                external_id = card.get("id", "")

                                data = {
                                    "board_id": board_id,
                                    "board_name": board_name,
                                    "idList": card.get("idList"),
                                    "shortLink": card.get("shortLink"),
                                    "badges": card.get("badges"),
                                    "labels": card.get("labels", []),
                                    "due": card.get("due"),
                                    "dueComplete": card.get("dueComplete"),
                                }

                                result = cls.upsert_item(
                                    db=db,
                                    connector_id=connector_id,
                                    item_type="card",
                                    external_id=external_id,
                                    title=card.get("name"),
                                    description=card.get("desc"),
                                    status="complete" if card.get("dueComplete") else "open",
                                    url=card.get("url"),
                                    user_id=user_id,
                                    org_id=org_id,
                                    data=data,
                                )

                                items_synced += 1
                                if result == "created":
                                    items_created += 1
                                else:
                                    items_updated += 1

                        except Exception as e:
                            logger.warning(
                                "trello_service.sync_cards.error",
                                board_id=board_id,
                                error=str(e),
                            )

            cls.update_sync_status(db=db, connector_id=connector_id, status="success")

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("trello_service.sync_items.error", error=str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        connection: Dict[str, Any],
        action: str,
        data: Dict[str, Any],
    ) -> WriteResult:
        """Perform write operation on Trello."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return WriteResult(success=False, error="No credentials found")

            api_key = credentials.get("api_key")
            api_token = credentials.get("api_token") or credentials.get("access_token")
            if not api_key or not api_token:
                return WriteResult(success=False, error="Missing API credentials")

            async with TrelloClient(api_key, api_token) as client:
                if action == "create_card":
                    list_id = data.get("list_id")
                    name = data.get("name")
                    desc = data.get("desc")

                    if not list_id or not name:
                        return WriteResult(
                            success=False, error="Missing list_id or name"
                        )

                    result = await client.create_card(list_id, name, desc=desc)

                    return WriteResult(
                        success=True,
                        item_id=result.get("id"),
                        url=result.get("url"),
                    )

                return WriteResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("trello_service.write_item.error", error=str(e))
            return WriteResult(success=False, error=str(e))

    @classmethod
    async def list_boards(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List Trello boards for the user."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            api_key = credentials.get("api_key")
            api_token = credentials.get("api_token") or credentials.get("access_token")
            if not api_key or not api_token:
                return []

            async with TrelloClient(api_key, api_token) as client:
                boards = await client.get_member_boards(filter="open")

                return [
                    {
                        "id": board.get("id"),
                        "name": board.get("name"),
                        "desc": board.get("desc"),
                        "url": board.get("url"),
                        "shortLink": board.get("shortLink"),
                        "closed": board.get("closed"),
                    }
                    for board in boards[:max_results]
                ]

        except Exception as e:
            logger.error("trello_service.list_boards.error", error=str(e))
            return []

    @classmethod
    async def list_my_cards(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List cards assigned to the current user."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            api_key = credentials.get("api_key")
            api_token = credentials.get("api_token") or credentials.get("access_token")
            if not api_key or not api_token:
                return []

            async with TrelloClient(api_key, api_token) as client:
                # Get member's cards
                member = await client.get_me()
                member_id = member.get("id")

                # List cards from open boards
                cards = []
                boards = await client.get_member_boards(filter="open")

                for board in boards[:5]:  # Check first 5 boards
                    board_id = board.get("id")
                    board_name = board.get("name")

                    try:
                        board_data = await client.get_board(
                            board_id, cards="open"
                        )
                        board_cards = board_data.get("cards", [])

                        for card in board_cards:
                            if member_id in card.get("idMembers", []):
                                cards.append({
                                    "id": card.get("id"),
                                    "name": card.get("name"),
                                    "desc": card.get("desc"),
                                    "url": card.get("url"),
                                    "board_name": board_name,
                                    "due": card.get("due"),
                                    "labels": card.get("labels", []),
                                })

                    except Exception:
                        pass

                return cards[:max_results]

        except Exception as e:
            logger.error("trello_service.list_my_cards.error", error=str(e))
            return []
