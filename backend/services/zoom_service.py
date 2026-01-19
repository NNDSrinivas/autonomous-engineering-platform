"""
Zoom service for NAVI connector integration.

Provides syncing and querying of Zoom recordings and transcripts.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, date, timedelta
import structlog

from backend.services.connector_base import ConnectorServiceBase

logger = structlog.get_logger(__name__)


class ZoomService(ConnectorServiceBase):
    """Service for Zoom meeting and recording integration."""

    PROVIDER = "zoom"
    SUPPORTED_ITEM_TYPES = ["recording", "meeting", "transcript"]
    WRITE_OPERATIONS = []

    @classmethod
    async def sync_items(
        cls,
        db,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """
        Sync Zoom recordings to local database.

        Args:
            db: Database session
            connection: Connector connection dict with credentials
            item_types: Types to sync (recording)
            **kwargs: Additional args (from_date, to_date)

        Returns:
            Dict with counts of synced items by type
        """
        from backend.integrations.zoom_client import ZoomClient

        config = connection.get("config", {})

        # Support both OAuth and Server-to-Server auth
        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        account_id = config.get("account_id")
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")

        user_id = connection.get("user_id")
        counts = {"recording": 0}

        # Parse expires_at if present
        expires_at = None
        if config.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(
                    str(config["expires_at"]).replace("Z", "+00:00")
                )
            except Exception:
                pass

        client = ZoomClient(
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        # Get date range
        to_date = kwargs.get("to_date", date.today())
        from_date = kwargs.get("from_date", to_date - timedelta(days=30))

        # Sync for the connected user
        zoom_user_id = kwargs.get("zoom_user_id", "me")
        recordings = client.list_recordings_for_user(
            user_id=zoom_user_id,
            from_date=from_date,
            to_date=to_date,
        )

        for meeting in recordings:
            meeting_id = meeting.get("uuid", "")
            topic = meeting.get("topic", "Untitled Meeting")
            start_time = meeting.get("start_time", "")

            cls.upsert_item(
                db=db,
                user_id=user_id,
                provider=cls.PROVIDER,
                item_type="recording",
                external_id=meeting_id,
                title=topic,
                url=meeting.get("share_url", ""),
                metadata={
                    "start_time": start_time,
                    "duration": meeting.get("duration"),
                    "total_size": meeting.get("total_size"),
                    "recording_count": len(meeting.get("recording_files", [])),
                },
            )
            counts["recording"] += 1

        logger.info(
            "zoom.sync_recordings",
            user_id=user_id,
            count=counts["recording"],
        )

        return counts

    @classmethod
    def list_recordings(
        cls,
        db,
        connection: Dict[str, Any],
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List Zoom recordings.

        Args:
            db: Database session
            connection: Connector connection dict
            from_date: Start date filter
            to_date: End date filter
            max_results: Maximum results to return

        Returns:
            List of recording dicts
        """
        from backend.integrations.zoom_client import ZoomClient

        config = connection.get("config", {})

        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        account_id = config.get("account_id")
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")

        # Parse expires_at if present
        expires_at = None
        if config.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(
                    str(config["expires_at"]).replace("Z", "+00:00")
                )
            except Exception:
                pass

        client = ZoomClient(
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        # Default date range
        if not to_date:
            to_date = date.today()
        if not from_date:
            from_date = to_date - timedelta(days=30)

        recordings = client.list_recordings_for_user(
            user_id="me",
            from_date=from_date,
            to_date=to_date,
            page_size=max_results,
        )

        return [
            {
                "id": m.get("uuid", ""),
                "topic": m.get("topic", "Untitled"),
                "start_time": m.get("start_time", ""),
                "duration": m.get("duration", 0),
                "share_url": m.get("share_url", ""),
                "recording_count": len(m.get("recording_files", [])),
            }
            for m in recordings
        ]

    @classmethod
    def get_transcript(
        cls,
        db,
        connection: Dict[str, Any],
        meeting: Dict[str, Any],
    ) -> Optional[str]:
        """
        Get transcript for a Zoom meeting.

        Args:
            db: Database session
            connection: Connector connection dict
            meeting: Meeting dict from list_recordings

        Returns:
            Transcript text or None
        """
        from backend.integrations.zoom_client import ZoomClient

        config = connection.get("config", {})

        access_token = config.get("access_token")
        refresh_token = config.get("refresh_token")
        account_id = config.get("account_id")
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")

        # Parse expires_at if present
        expires_at = None
        if config.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(
                    str(config["expires_at"]).replace("Z", "+00:00")
                )
            except Exception:
                pass

        client = ZoomClient(
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        return client.get_meeting_transcript_text(meeting)
