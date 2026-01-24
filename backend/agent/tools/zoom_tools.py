"""
Zoom tools for NAVI agent.

Provides tools to query Zoom recordings and transcripts.
"""

from typing import Any, Dict
from datetime import date, timedelta
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_zoom_recordings(
    context: Dict[str, Any],
    days_back: int = 30,
    max_results: int = 20,
) -> ToolResult:
    """List recent Zoom recordings."""
    from backend.services.zoom_service import ZoomService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "zoom")

        if not connection:
            return ToolResult(
                output="Zoom is not connected. Please connect your Zoom account first.",
                sources=[],
            )

        to_date = date.today()
        from_date = to_date - timedelta(days=days_back)

        recordings = ZoomService.list_recordings(
            db=db,
            connection=connection,
            from_date=from_date,
            to_date=to_date,
            max_results=max_results,
        )

        if not recordings:
            return ToolResult(
                output=f"No Zoom recordings found in the last {days_back} days.",
                sources=[],
            )

        lines = [f"Found {len(recordings)} recording(s):\n"]
        sources = []

        for rec in recordings:
            topic = rec.get("topic", "Untitled")
            start = rec.get("start_time", "")[:10] if rec.get("start_time") else ""
            duration = rec.get("duration", 0)
            url = rec.get("share_url", "")

            # Format duration
            hours = duration // 60
            mins = duration % 60
            duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

            lines.append(f"- 🎥 **{topic}**")
            lines.append(f"  - Date: {start} | Duration: {duration_str}")
            if url:
                lines.append(f"  - [View Recording]({url})")
            lines.append("")

            if url:
                sources.append({"type": "zoom_recording", "name": topic, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_zoom_recordings.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_zoom_transcript(
    context: Dict[str, Any],
    meeting_id: str,
) -> ToolResult:
    """Get transcript for a Zoom meeting."""
    from backend.services.zoom_service import ZoomService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "zoom")

        if not connection:
            return ToolResult(output="Zoom is not connected.", sources=[])

        # First get the meeting details
        recordings = ZoomService.list_recordings(
            db=db,
            connection=connection,
            from_date=date.today() - timedelta(days=90),
            to_date=date.today(),
            max_results=100,
        )

        # Find the meeting
        meeting = None
        for rec in recordings:
            if rec.get("id") == meeting_id:
                meeting = rec
                break

        if not meeting:
            return ToolResult(
                output=f"Could not find meeting {meeting_id}.",
                sources=[],
            )

        transcript = ZoomService.get_transcript(
            db=db,
            connection=connection,
            meeting=meeting,
        )

        if not transcript:
            return ToolResult(
                output=f"No transcript available for meeting '{meeting.get('topic', 'Untitled')}'.",
                sources=[],
            )

        # Truncate if too long
        if len(transcript) > 5000:
            transcript = transcript[:5000] + "\n\n... (transcript truncated)"

        return ToolResult(
            output=f"# Transcript: {meeting.get('topic', 'Untitled')}\n\n{transcript}",
            sources=[],
        )

    except Exception as e:
        logger.error("get_zoom_transcript.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def search_zoom_recordings(
    context: Dict[str, Any],
    search_term: str,
    days_back: int = 90,
) -> ToolResult:
    """Search Zoom recordings by topic."""
    from backend.services.zoom_service import ZoomService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "zoom")

        if not connection:
            return ToolResult(output="Zoom is not connected.", sources=[])

        to_date = date.today()
        from_date = to_date - timedelta(days=days_back)

        recordings = ZoomService.list_recordings(
            db=db,
            connection=connection,
            from_date=from_date,
            to_date=to_date,
            max_results=100,
        )

        # Filter by search term
        search_lower = search_term.lower()
        matches = [
            rec for rec in recordings if search_lower in rec.get("topic", "").lower()
        ]

        if not matches:
            return ToolResult(
                output=f"No recordings found matching '{search_term}'.",
                sources=[],
            )

        lines = [f"Found {len(matches)} recording(s) matching '{search_term}':\n"]
        sources = []

        for rec in matches:
            topic = rec.get("topic", "Untitled")
            start = rec.get("start_time", "")[:10] if rec.get("start_time") else ""
            url = rec.get("share_url", "")

            lines.append(f"- 🎥 **{topic}**")
            lines.append(f"  - Date: {start}")
            if url:
                lines.append(f"  - [View Recording]({url})")
            lines.append("")

            if url:
                sources.append({"type": "zoom_recording", "name": topic, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("search_zoom_recordings.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


ZOOM_TOOLS = {
    "zoom.list_recordings": list_zoom_recordings,
    "zoom.get_transcript": get_zoom_transcript,
    "zoom.search_recordings": search_zoom_recordings,
}
