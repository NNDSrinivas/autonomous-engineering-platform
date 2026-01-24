"""
Monday.com tools for NAVI agent.

Provides tools to query and manage Monday.com boards and items.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_monday_boards(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Monday.com boards."""
    from backend.services.monday_service import MondayService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "monday")

        if not connection:
            return ToolResult(
                output="Monday.com is not connected. Please connect your Monday.com account first.",
                sources=[],
            )

        boards = await MondayService.list_boards(
            db=db, connection=connection, max_results=max_results
        )

        if not boards:
            return ToolResult(output="No Monday.com boards found.", sources=[])

        lines = [f"Found {len(boards)} board(s):\n"]
        sources = []

        state_emoji = {
            "active": "✅",
            "archived": "📦",
            "deleted": "🗑️",
        }

        for b in boards:
            name = b.get("name", "Untitled")
            state = b.get("state", "")
            kind = b.get("board_kind", "")
            url = b.get("url", "")

            emoji = state_emoji.get(state, "📋")
            lines.append(f"- {emoji} **{name}**")
            if kind:
                lines.append(f"  - Type: {kind}")
            if url:
                lines.append(f"  - [Open Board]({url})")
            lines.append("")

            if url:
                sources.append({"type": "monday_board", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_monday_boards.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def list_monday_items(
    context: Dict[str, Any],
    board_id: int,
    max_results: int = 50,
) -> ToolResult:
    """List items in a Monday.com board."""
    from backend.services.monday_service import MondayService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "monday")

        if not connection:
            return ToolResult(output="Monday.com is not connected.", sources=[])

        items = await MondayService.list_items(
            db=db,
            connection=connection,
            board_id=board_id,
            max_results=max_results,
        )

        if not items:
            return ToolResult(
                output=f"No items found in board {board_id}.",
                sources=[],
            )

        lines = [f"Found {len(items)} item(s):\n"]
        sources = []

        # Group by group
        by_group = {}
        for item in items:
            group = item.get("group", "No Group")
            if group not in by_group:
                by_group[group] = []
            by_group[group].append(item)

        for group, group_items in by_group.items():
            lines.append(f"## {group}\n")

            for item in group_items:
                name = item.get("name", "Untitled")
                state = item.get("state", "")
                url = item.get("url", "")

                state_emoji = "✅" if state == "active" else "📦"
                lines.append(f"- {state_emoji} **{name}**")
                if url:
                    lines.append(f"  - [Open Item]({url})")

                if url:
                    sources.append({"type": "monday_item", "name": name, "url": url})

            lines.append("")

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_monday_items.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_monday_my_items(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """Get Monday.com items assigned to me."""
    from backend.services.monday_service import MondayService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "monday")

        if not connection:
            return ToolResult(output="Monday.com is not connected.", sources=[])

        items = await MondayService.get_my_items(
            db=db,
            connection=connection,
            max_results=max_results,
        )

        if not items:
            return ToolResult(
                output="No items assigned to you.",
                sources=[],
            )

        lines = [f"# My Items ({len(items)})\n"]
        sources = []

        # Group by board
        by_board = {}
        for item in items:
            board = item.get("board_name", "Unknown Board")
            if board not in by_board:
                by_board[board] = []
            by_board[board].append(item)

        for board, board_items in by_board.items():
            lines.append(f"## {board}\n")

            for item in board_items:
                name = item.get("name", "Untitled")
                group = item.get("group", "")
                url = item.get("url", "")

                lines.append(f"- 📋 **{name}**")
                if group:
                    lines.append(f"  - Group: {group}")
                if url:
                    lines.append(f"  - [Open Item]({url})")

                if url:
                    sources.append({"type": "monday_item", "name": name, "url": url})

            lines.append("")

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_monday_my_items.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_monday_item(
    context: Dict[str, Any],
    item_id: int,
) -> ToolResult:
    """Get details of a Monday.com item."""
    from backend.services.monday_service import MondayService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "monday")

        if not connection:
            return ToolResult(output="Monday.com is not connected.", sources=[])

        item = await MondayService.get_item(
            db=db,
            connection=connection,
            item_id=item_id,
        )

        if not item:
            return ToolResult(
                output=f"Could not find item {item_id}.",
                sources=[],
            )

        name = item.get("name", "Untitled")
        board_name = item.get("board_name", "")
        group = item.get("group", "")
        url = item.get("url", "")
        column_values = item.get("column_values", [])
        updates = item.get("updates", [])

        lines = [f"# {name}\n"]

        if board_name:
            lines.append(f"**Board:** {board_name}")
        if group:
            lines.append(f"**Group:** {group}")

        if column_values:
            lines.append("\n**Fields:**")
            for cv in column_values:
                text = cv.get("text", "")
                if text:
                    col_id = cv.get("id", "")
                    lines.append(f"  - {col_id}: {text}")

        if updates:
            lines.append("\n**Updates:**")
            for u in updates[:5]:  # Show last 5 updates
                body = u.get("body", "")[:200]
                creator = u.get("creator", "")
                created = u.get("created_at", "")[:10] if u.get("created_at") else ""
                lines.append(f"  - {creator} ({created}): {body}")

        sources = []
        if url:
            sources.append({"type": "monday_item", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_monday_item.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def create_monday_item(
    context: Dict[str, Any],
    board_id: int,
    item_name: str,
    group_id: Optional[str] = None,
) -> ToolResult:
    """Create a new Monday.com item (requires approval)."""
    from backend.services.monday_service import MondayService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "monday")

        if not connection:
            return ToolResult(output="Monday.com is not connected.", sources=[])

        result = await MondayService.write_item(
            db=db,
            connection=connection,
            operation="create_item",
            board_id=board_id,
            item_name=item_name,
            group_id=group_id,
        )

        if result.get("success"):
            item_id = result.get("item_id", "")
            url = f"https://monday.com/boards/{board_id}/pulses/{item_id}"
            return ToolResult(
                output=f"Item '{item_name}' created successfully.\n\n[Open Item]({url})",
                sources=[{"type": "monday_item", "name": item_name, "url": url}],
            )
        else:
            return ToolResult(output="Failed to create item.", sources=[])

    except Exception as e:
        logger.error("create_monday_item.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


MONDAY_TOOLS = {
    "monday.list_boards": list_monday_boards,
    "monday.list_items": list_monday_items,
    "monday.get_my_items": get_monday_my_items,
    "monday.get_item": get_monday_item,
    "monday.create_item": create_monday_item,
}
