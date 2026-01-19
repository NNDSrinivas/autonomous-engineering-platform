"""
Loom service for NAVI integration.

Provides sync, query operations for Loom videos and transcripts.
"""

from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.orm import Session

from backend.services.connector_base import (
    ConnectorServiceBase,
    SyncResult,
    WriteResult,
)
from backend.integrations.loom_client import LoomClient

logger = structlog.get_logger(__name__)


class LoomService(ConnectorServiceBase):
    """
    Loom connector service for NAVI.

    Supports:
    - Videos (list, search)
    - Transcripts (get)
    """

    PROVIDER = "loom"
    SUPPORTED_ITEM_TYPES = ["video"]
    WRITE_OPERATIONS = []  # Loom API is mostly read-only

    @classmethod
    async def sync_items(
        cls,
        db: Session,
        connection: Dict[str, Any],
        item_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """Sync videos from Loom."""
        logger.info("loom_service.sync_items.start", connector_id=connection.get("id"))

        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return SyncResult(success=False, error="No credentials found")

            access_token = credentials.get("access_token")
            if not access_token:
                return SyncResult(success=False, error="No access token")

            connector_id = connection.get("id")
            user_id = connection.get("user_id")
            org_id = connection.get("org_id")

            items_synced = 0
            items_created = 0
            items_updated = 0

            async with LoomClient(access_token) as client:
                videos_data = await client.list_videos(page_size=100)
                videos = videos_data.get("videos", [])

                for video in videos:
                    external_id = video.get("id", "")

                    data = {
                        "share_url": video.get("share_url"),
                        "embed_url": video.get("embed_url"),
                        "thumbnail_url": video.get("thumbnail_url"),
                        "duration": video.get("duration"),
                        "privacy": video.get("privacy"),
                        "source": video.get("source"),
                        "views": video.get("view_count"),
                        "created_at": video.get("created_at"),
                    }

                    result = cls.upsert_item(
                        db=db,
                        connector_id=connector_id,
                        item_type="video",
                        external_id=external_id,
                        title=video.get("name"),
                        description=video.get("description"),
                        status=video.get("privacy", "private"),
                        url=video.get("share_url"),
                        user_id=user_id,
                        org_id=org_id,
                        data=data,
                    )

                    items_synced += 1
                    if result == "created":
                        items_created += 1
                    else:
                        items_updated += 1

            cls.update_sync_status(db=db, connector_id=connector_id, status="success")

            return SyncResult(
                success=True,
                items_synced=items_synced,
                items_created=items_created,
                items_updated=items_updated,
            )

        except Exception as e:
            logger.error("loom_service.sync_items.error", error=str(e))
            return SyncResult(success=False, error=str(e))

    @classmethod
    async def write_item(
        cls,
        db: Session,
        connection: Dict[str, Any],
        action: str,
        data: Dict[str, Any],
    ) -> WriteResult:
        """Loom API is mostly read-only."""
        return WriteResult(success=False, error="Write operations not supported for Loom")

    @classmethod
    async def list_videos(
        cls,
        db: Session,
        connection: Dict[str, Any],
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List Loom videos."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                return []

            async with LoomClient(access_token) as client:
                videos_data = await client.list_videos(page_size=max_results)
                videos = videos_data.get("videos", [])

                return [
                    {
                        "id": video.get("id"),
                        "name": video.get("name"),
                        "description": video.get("description"),
                        "share_url": video.get("share_url"),
                        "thumbnail_url": video.get("thumbnail_url"),
                        "duration": video.get("duration"),
                        "views": video.get("view_count"),
                        "created_at": video.get("created_at"),
                    }
                    for video in videos[:max_results]
                ]

        except Exception as e:
            logger.error("loom_service.list_videos.error", error=str(e))
            return []

    @classmethod
    async def get_transcript(
        cls,
        db: Session,
        connection: Dict[str, Any],
        video_id: str,
    ) -> Optional[str]:
        """Get transcript for a Loom video."""
        try:
            credentials = cls.get_credentials(connection)
            if not credentials:
                return None

            access_token = credentials.get("access_token")
            if not access_token:
                return None

            async with LoomClient(access_token) as client:
                transcript_data = await client.get_transcript(video_id)

                # Extract text from transcript segments
                segments = transcript_data.get("transcript", [])
                if isinstance(segments, list):
                    text_parts = [seg.get("text", "") for seg in segments if seg.get("text")]
                    return " ".join(text_parts)
                elif isinstance(segments, str):
                    return segments

                return None

        except Exception as e:
            logger.error("loom_service.get_transcript.error", error=str(e))
            return None

    @classmethod
    async def search_videos(
        cls,
        db: Session,
        connection: Dict[str, Any],
        query: str,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Loom videos by name/description."""
        try:
            # Get all videos and filter locally (Loom API has limited search)
            videos = await cls.list_videos(db, connection, max_results=100)

            query_lower = query.lower()
            filtered = [
                v for v in videos
                if query_lower in (v.get("name", "").lower()) or
                   query_lower in (v.get("description", "") or "").lower()
            ]

            return filtered[:max_results]

        except Exception as e:
            logger.error("loom_service.search_videos.error", error=str(e))
            return []
