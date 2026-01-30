"""
Google Calendar tools for NAVI agent.

Provides tools to query Google Calendar events.
"""

from typing import Any, Dict
from datetime import datetime, timezone
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


async def list_upcoming_events(
    context: Dict[str, Any],
    days: int = 7,
    max_results: int = 20,
) -> ToolResult:
    """List upcoming Google Calendar events."""
    from backend.services.google_calendar_service import GoogleCalendarService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "google_calendar")

        if not connection:
            return ToolResult(
                output="Google Calendar is not connected. Please connect your Google account first.",
                sources=[],
            )

        events = await GoogleCalendarService.get_upcoming_events(
            db=db,
            connection=connection,
            days=days,
            max_results=max_results,
        )

        if not events:
            return ToolResult(
                output=f"No upcoming events in the next {days} days.",
                sources=[],
            )

        lines = [f"# Upcoming Events (Next {days} Days)\n"]
        sources = []

        current_date = None

        for e in events:
            summary = e.get("summary", "Untitled Event")
            start = e.get("start", "")
            location = e.get("location", "")
            url = e.get("html_link", "")

            # Parse start time
            if "T" in start:
                # DateTime format
                try:
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    event_date = dt.strftime("%A, %B %d")
                    event_time = dt.strftime("%I:%M %p")
                except Exception:
                    event_date = start[:10]
                    event_time = ""
            else:
                # All-day event
                event_date = start
                event_time = "All day"

            # Group by date
            if event_date != current_date:
                current_date = event_date
                lines.append(f"\n## {event_date}\n")

            lines.append(f"- 📅 **{summary}**")
            if event_time:
                lines.append(f"  - Time: {event_time}")
            if location:
                lines.append(f"  - Location: {location}")
            if url:
                lines.append(f"  - [Open in Calendar]({url})")

            if url:
                sources.append(
                    {"type": "google_calendar_event", "name": summary, "url": url}
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("list_upcoming_events.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_todays_events(
    context: Dict[str, Any],
) -> ToolResult:
    """Get today's Google Calendar events."""
    from backend.services.google_calendar_service import GoogleCalendarService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "google_calendar")

        if not connection:
            return ToolResult(output="Google Calendar is not connected.", sources=[])

        events = await GoogleCalendarService.get_todays_events(
            db=db,
            connection=connection,
        )

        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

        if not events:
            return ToolResult(
                output=f"# Today's Schedule ({today})\n\nNo events scheduled for today.",
                sources=[],
            )

        lines = [f"# Today's Schedule ({today})\n"]
        sources = []

        for e in events:
            summary = e.get("summary", "Untitled Event")
            start = e.get("start", "")
            end = e.get("end", "")
            location = e.get("location", "")
            url = e.get("html_link", "")
            attendees = e.get("attendees", [])

            # Parse times
            if "T" in start:
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    start_time = start_dt.strftime("%I:%M %p")
                except Exception:
                    start_time = ""

                try:
                    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    end_time = end_dt.strftime("%I:%M %p")
                except Exception:
                    end_time = ""

                time_str = (
                    f"{start_time} - {end_time}"
                    if start_time and end_time
                    else start_time
                )
            else:
                time_str = "All day"

            lines.append(f"- 📅 **{summary}**")
            lines.append(f"  - Time: {time_str}")
            if location:
                lines.append(f"  - Location: {location}")
            if attendees:
                attendee_count = len(attendees)
                lines.append(f"  - Attendees: {attendee_count}")
            if url:
                lines.append(f"  - [Open in Calendar]({url})")
            lines.append("")

            if url:
                sources.append(
                    {"type": "google_calendar_event", "name": summary, "url": url}
                )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_todays_events.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


async def get_event_details(
    context: Dict[str, Any],
    event_id: str,
) -> ToolResult:
    """Get details of a specific calendar event."""
    from backend.services.google_calendar_service import GoogleCalendarService
    from backend.services.connectors import get_connector
    from backend.database.session import get_db

    user_id = context.get("user_id")
    if not user_id:
        return ToolResult(output="Error: No user ID in context.", sources=[])

    try:
        db = next(get_db())
        connection = get_connector(db, user_id, "google_calendar")

        if not connection:
            return ToolResult(output="Google Calendar is not connected.", sources=[])

        # Get all upcoming events and find the one we want
        events = await GoogleCalendarService.get_upcoming_events(
            db=db,
            connection=connection,
            days=30,
            max_results=100,
        )

        event = None
        for e in events:
            if e.get("id") == event_id:
                event = e
                break

        if not event:
            return ToolResult(
                output=f"Could not find event {event_id}.",
                sources=[],
            )

        summary = event.get("summary", "Untitled Event")
        description = event.get("description", "")
        location = event.get("location", "")
        start = event.get("start", "")
        end = event.get("end", "")
        organizer = event.get("organizer", "")
        attendees = event.get("attendees", [])
        url = event.get("html_link", "")

        lines = [f"# {summary}\n"]

        if start:
            lines.append(f"**Start:** {start}")
        if end:
            lines.append(f"**End:** {end}")
        if location:
            lines.append(f"**Location:** {location}")
        if organizer:
            lines.append(f"**Organizer:** {organizer}")

        if attendees:
            lines.append("\n**Attendees:**")
            for a in attendees:
                email = a.get("email", "")
                response = a.get("response", "")
                status_emoji = {
                    "accepted": "✅",
                    "declined": "❌",
                    "tentative": "❓",
                    "needsAction": "⏳",
                }.get(response, "❓")
                lines.append(f"  - {status_emoji} {email}")

        if description:
            lines.append(f"\n**Description:**\n{description}")

        sources = []
        if url:
            sources.append(
                {"type": "google_calendar_event", "name": summary, "url": url}
            )

        return ToolResult(output="\n".join(lines), sources=sources)

    except Exception as e:
        logger.error("get_event_details.error", error=str(e))
        return ToolResult(output=f"Error: {e}", sources=[])


GOOGLE_CALENDAR_TOOLS = {
    "gcalendar_list_events": list_upcoming_events,
    "gcalendar_todays_events": get_todays_events,
    "gcalendar_get_event": get_event_details,
}
