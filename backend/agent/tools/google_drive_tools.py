"""
Google Drive tools for NAVI agent.

Provides tools to query and search Google Drive files.
"""

from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_google_drive_files(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List recent Google Drive files."""
    from backend.services.google_drive_service import GoogleDriveService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "google_drive")

        if not connection:
            return ToolResult(
                output="Google Drive is not connected. Please connect your Google account first.",
                sources=[],
            )

        files = await GoogleDriveService.list_recent_files(
            db=db, connection=connection, max_results=max_results
        )

        if not files:
            return ToolResult(output="No Google Drive files found.", sources=[])

        lines = [f"Found {len(files)} file(s):\n"]
        sources = []

        type_emoji = {
            "application/vnd.google-apps.document": "📄",
            "application/vnd.google-apps.spreadsheet": "📊",
            "application/vnd.google-apps.presentation": "📽️",
            "application/vnd.google-apps.folder": "📁",
            "application/pdf": "📕",
        }

        for f in files:
            name = f.get("name", "Untitled")
            mime = f.get("mime_type", "")
            url = f.get("url", "")
            modified = f.get("modified_time", "")[:10] if f.get("modified_time") else ""

            emoji = type_emoji.get(mime, "📄")
            lines.append(f"- {emoji} **{name}**")
            if modified:
                lines.append(f"  - Modified: {modified}")
            if url:
                lines.append(f"  - [Open in Drive]({url})")
            lines.append("")

            if url:
                sources.append({"type": "google_drive_file", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_google_drive_files.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def search_google_drive(
    context: Dict[str, Any],
    search_term: str,
    file_type: Optional[str] = None,
    max_results: int = 20,
) -> ToolResult:
    """Search Google Drive files."""
    from backend.services.google_drive_service import GoogleDriveService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "google_drive")

        if not connection:
            return ToolResult(output="Google Drive is not connected.", sources=[])

        files = await GoogleDriveService.search_files(
            db=db,
            connection=connection,
            search_term=search_term,
            file_type=file_type,
            max_results=max_results,
        )

        if not files:
            return ToolResult(
                output=f"No files found matching '{search_term}'.",
                sources=[],
            )

        lines = [f"Found {len(files)} file(s) matching '{search_term}':\n"]
        sources = []

        type_emoji = {
            "application/vnd.google-apps.document": "📄",
            "application/vnd.google-apps.spreadsheet": "📊",
            "application/vnd.google-apps.presentation": "📽️",
            "application/vnd.google-apps.folder": "📁",
            "application/pdf": "📕",
        }

        for f in files:
            name = f.get("name", "Untitled")
            mime = f.get("mime_type", "")
            url = f.get("url", "")

            emoji = type_emoji.get(mime, "📄")
            lines.append(f"- {emoji} **{name}**")
            if url:
                lines.append(f"  - [Open in Drive]({url})")
            lines.append("")

            if url:
                sources.append({"type": "google_drive_file", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("search_google_drive.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_google_drive_file_content(
    context: Dict[str, Any],
    file_id: str,
) -> ToolResult:
    """Get the content of a Google Drive file."""
    from backend.services.google_drive_service import GoogleDriveService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "google_drive")

        if not connection:
            return ToolResult(output="Google Drive is not connected.", sources=[])

        content = await GoogleDriveService.get_file_content(
            db=db, connection=connection, file_id=file_id
        )

        if not content:
            return ToolResult(
                output=f"Could not retrieve content for file {file_id}. The file may be empty or in an unsupported format.",
                sources=[],
            )

        # Truncate if too long
        if len(content) > 5000:
            content = content[:5000] + "\n\n... (content truncated)"

        return ToolResult(
            output=f"# File Content\n\n{content}",
            sources=[],
        )

    except Exception as e:
        logger.error("get_google_drive_file_content.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


GOOGLE_DRIVE_TOOLS = {
    "gdrive_list_files": list_google_drive_files,
    "gdrive_search": search_google_drive,
    "gdrive_get_content": get_google_drive_file_content,
}
