"""
Google Calendar service for NAVI connector integration.

Provides syncing and querying of Google Calendar events.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class GoogleCalendarService(ConnectorServiceBase):
    """Service for Google Calendar integration."""

    PROVIDER = "google_calendar"
    SUPPORTED_ITEM_TYPES = ["event"]
    WRITE_OPERATIONS = ["create_event", "update_event", "delete_event"]

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Google Calendar events to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (event)
            **kwargs: Additional args (calendar_id, time_min, time_max)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.google_calendar_client import GoogleCalendarClient
        from backend.core.config import settings

        config = connection.get("config", {})
        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        expires_at = config.get("expires_at")

        if not access_token and not refresh_token:
            raise ValueError("Google Calendar credentials not configured")

        user_id = connection.get("user_id")
        counts = {"event": 0}

        client = GoogleCalendarClient(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        calendar_id = kwargs.get("calendar_id", "primary")
        time_min = kwargs.get("time_min", datetime.now(timezone.utc))
        time_max = kwargs.get("time_max", time_min + timedelta(days=30))

        events = await client.list_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=100,
        )

        for event in events:
            event_id = event.get("id", "")
            summary = event.get("summary", "Untitled Event")

            # Get start time
            start = event.get("start", {})
            start_time = start.get("dateTime") or start.get("date", "")

            cls.upsert_item(
                db=db,
                user_id=user_id,
                provider=cls.PROVIDER,
                item_type="event",
                external_id=event_id,
                title=summary,
                url=event.get("htmlLink", ""),
                metadata={
                    "start": start_time,
                    "end": event.get("end", {}).get("dateTime")
                    or event.get("end", {}).get("date", ""),
                    "status": event.get("status"),
                    "organizer": event.get("organizer", {}).get("email"),
                    "location": event.get("location"),
                },
            )
            counts["event"] += 1

        logger.info(
            "google_calendar.sync_events",
            user_id=user_id,
            count=counts["event"],
        )

        return counts

    @classmethod
    async def list_events(
        cls,
        db,
        connection: Dict[str, Any],
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Google Calendar events.

        Args:
            db: Database session
            connection: Connector connection dict
            calendar_id: Calendar ID (default: primary)
            time_min: Start time filter
            time_max: End time filter
            max_results: Maximum results to return

        Returns:
            List of event dicts
        """
        from backend.integrations.google_calendar_client import GoogleCalendarClient
        from backend.core.config import settings

        config = connection.get("config", {})
        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        expires_at = config.get("expires_at")

        if not access_token and not refresh_token:
            return []

        client = GoogleCalendarClient(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        # Default to next 7 days
        if not time_min:
            time_min = datetime.now(timezone.utc)
        if not time_max:
            time_max = time_min + timedelta(days=7)

        events = await client.list_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

        return [
            {
                "id": e.get("id", ""),
                "summary": e.get("summary", "Untitled Event"),
                "start": e.get("start", {}).get("dateTime")
                or e.get("start", {}).get("date", ""),
                "end": e.get("end", {}).get("dateTime")
                or e.get("end", {}).get("date", ""),
                "location": e.get("location", ""),
                "description": e.get("description", ""),
                "status": e.get("status", ""),
                "organizer": e.get("organizer", {}).get("email", ""),
                "html_link": e.get("htmlLink", ""),
                "attendees": [
                    {
                        "email": a.get("email", ""),
                        "response": a.get("responseStatus", ""),
                    }
                    for a in e.get("attendees", [])
                ],
            }
            for e in events
        ]

    @classmethod
    async def get_upcoming_events(
        cls,
        db,
        connection: Dict[str, Any],
        days: int = 7,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming calendar events.

        Args:
            db: Database session
            connection: Connector connection dict
            days: Number of days to look ahead
            max_results: Maximum results to return

        Returns:
            List of upcoming events
        """
        time_min = datetime.now(timezone.utc)
        time_max = time_min + timedelta(days=days)

        return await cls.list_events(
            db=db,
            connection=connection,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

    @classmethod
    async def get_todays_events(
        cls,
        db,
        connection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Get today's calendar events.

        Args:
            db: Database session
            connection: Connector connection dict

        Returns:
            List of today's events
        """
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return await cls.list_events(
            db=db,
            connection=connection,
            time_min=start_of_day,
            time_max=end_of_day,
            max_results=50,
        )
