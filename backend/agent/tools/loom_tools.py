"""
Loom tools for NAVI agent.

Provides tools to query Loom videos and transcripts.
"""

from typing import Any, Dict
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_loom_videos(
    context: Dict[str, Any],
    max_results: int = 20,
) -> ToolResult:
    """List Loom videos."""
    from backend.services.loom_service import LoomService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "loom")

        if not connection:
            return ToolResult(
                output="Loom is not connected. Please connect your Loom account first.",
                sources=[],
            )

        videos = await LoomService.list_videos(
            db=db, connection=connection, max_results=max_results
        )

        if not videos:
            return ToolResult(output="No Loom videos found.", sources=[])

        lines = [f"Found {len(videos)} Loom video(s):\n"]
        sources = []

        for video in videos:
            name = video.get("name", "Untitled")
            url = video.get("share_url", "")
            duration = video.get("duration", 0)
            views = video.get("views", 0)

            # Format duration
            mins = duration // 60
            secs = duration % 60
            duration_str = f"{mins}:{secs:02d}" if duration else "Unknown"

            lines.append(f"- **{name}**")
            lines.append(f"  - Duration: {duration_str} | Views: {views}")
            if url:
                lines.append(f"  - [Watch Video]({url})")
            lines.append("")

            if url:
                sources.append({"type": "loom_video", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_loom_videos.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_loom_transcript(
    context: Dict[str, Any],
    video_id: str,
) -> ToolResult:
    """Get transcript for a Loom video."""
    from backend.services.loom_service import LoomService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "loom")

        if not connection:
            return ToolResult(output="Loom is not connected.", sources=[])

        transcript = await LoomService.get_transcript(
            db=db, connection=connection, video_id=video_id
        )

        if not transcript:
            return ToolResult(
                output=f"No transcript available for video {video_id}.",
                sources=[],
            )

        # Truncate if too long
        if len(transcript) > 4000:
            transcript = transcript[:4000] + "... [truncated]"

        lines = [
            f"**Transcript for video {video_id}:**\n",
            transcript,
        ]

        return ToolResult(
            output="\n".join(lines),
            sources=[{
                "type": "loom_video",
                "name": f"Video {video_id}",
                "url": f"https://www.loom.com/share/{video_id}",
            }],
        )

    except Exception as e:
        logger.error("get_loom_transcript.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def search_loom_videos(
    context: Dict[str, Any],
    query: str,
    max_results: int = 20,
) -> ToolResult:
    """Search Loom videos by name or description."""
    from backend.services.loom_service import LoomService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "loom")

        if not connection:
            return ToolResult(output="Loom is not connected.", sources=[])

        videos = await LoomService.search_videos(
            db=db, connection=connection, query=query, max_results=max_results
        )

        if not videos:
            return ToolResult(
                output=f"No Loom videos found matching '{query}'.",
                sources=[],
            )

        lines = [f"Found {len(videos)} video(s) matching '{query}':\n"]
        sources = []

        for video in videos:
            name = video.get("name", "Untitled")
            url = video.get("share_url", "")
            description = video.get("description", "")

            lines.append(f"- **{name}**")
            if description:
                lines.append(f"  - {description[:100]}...")
            if url:
                lines.append(f"  - [Watch Video]({url})")
            lines.append("")

            if url:
                sources.append({"type": "loom_video", "name": name, "url": url})

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("search_loom_videos.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


LOOM_TOOLS = {
    "loom.list_videos": list_loom_videos,
    "loom.get_transcript": get_loom_transcript,
    "loom.search_videos": search_loom_videos,
}
