"""
Trello tools for NAVI agent.

Provides tools to query and manage Trello boards, lists, and cards.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_trello_boards(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Trello boards for the user."""
    from backend.services.trello_service import TrelloService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "trello")

        if not connection:
            return ToolResult(
                output="Trello is not connected. Please connect your Trello account first.",
                sources=[],
            )

        boards = await TrelloService.list_boards(
            db=db, connection=connection, max_results=max_results
        )

        if not boards:
            return ToolResult(output="No Trello boards found.", sources=[])

        lines = [f"Found {len(boards)} Trello board(s):\n"]
        sources = []

        for board in boards:
            name = board.get("name", "Unnamed")
            url = board.get("url", "")
            desc = board.get("desc", "")

            lines.append(f"- **{name}**")
            if desc:
                lines.append(f"  - {desc[:100]}...")
            if url:
                lines.append(f"  - [Open Board]({url})")
            lines.append("")

            if url:
                sources.append({"type": "trello_board", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_trello_boards.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_my_trello_cards(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Trello cards assigned to the current user."""
    from backend.services.trello_service import TrelloService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "trello")

        if not connection:
            return ToolResult(
                output="Trello is not connected. Please connect your Trello account first.",
                sources=[],
            )

        cards = await TrelloService.list_my_cards(
            db=db, connection=connection, max_results=max_results
        )

        if not cards:
            return ToolResult(output="No Trello cards assigned to you.", sources=[])

        lines = [f"Found {len(cards)} card(s) assigned to you:\n"]
        sources = []

        for card in cards:
            name = card.get("name", "Unnamed")
            url = card.get("url", "")
            board_name = card.get("board_name", "Unknown Board")
            due = card.get("due")
            labels = card.get("labels", [])

            lines.append(f"- **{name}**")
            lines.append(f"  - Board: {board_name}")
            if due:
                lines.append(f"  - Due: {due[:10]}")
            if labels:
                label_names = [lbl.get("name") or lbl.get("color") for lbl in labels]
                lines.append(f"  - Labels: {', '.join(label_names)}")
            if url:
                lines.append(f"  - [Open Card]({url})")
            lines.append("")

            if url:
                sources.append({"type": "trello_card", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_my_trello_cards.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def create_trello_card(
    context: Dict[str, Any],
    list_id: str,
    name: str,
    desc: Optional[str] = None,
    approve: bool = False,
) -> ToolResult:
    """Create a new Trello card."""
    from backend.services.trello_service import TrelloService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    if not approve:
        return ToolResult(
            output=f"**Preview: Create Trello Card**\n\n"
            f"List ID: {list_id}\n"
            f"Name: {name}\n"
            f"Description: {desc or 'None'}\n\n"
            f"Please approve this action to create the card.",
            sources=[],
        )

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "trello")

        if not connection:
            return ToolResult(
                output="Trello is not connected.",
                sources=[],
            )

        result = await TrelloService.write_item(
            db=db,
            connection=connection,
            action="create_card",
            data={"list_id": list_id, "name": name, "desc": desc},
        )

        if result.success:
            return ToolResult(
                output=f"Card '{name}' created successfully.",
                sources=[
                    {
                        "type": "trello_card",
                        "name": name,
                        "url": result.url or "",
                    }
                ],
            )
        else:
            return ToolResult(output=f"Failed: {result.error}", sources=[])

    except Exception as e:
        logger.error("create_trello_card.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


TRELLO_TOOLS = {
    "trello_list_boards": list_trello_boards,
    "trello_list_my_cards": list_my_trello_cards,
    "trello_create_card": create_trello_card,
}
