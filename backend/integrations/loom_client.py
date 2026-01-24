"""
Loom API client for video content access and management.

Provides access to Loom videos, workspaces, and members.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class LoomClient:
    """
    Async Loom API client.

    Supports:
    - Video listing and metadata
    - Workspace management
    - Video embeddings
    - Transcripts
    """

    BASE_URL = "https://api.loom.com/v1"

    def __init__(
        self,
        access_token: str,
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "LoomClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def get_authenticated_user(self) -> Dict[str, Any]:
        """Get the authenticated user info."""
        resp = await self.client.get("/users/me")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Videos
    # -------------------------------------------------------------------------

    async def list_videos(
        self,
        page_size: int = 25,
        cursor: Optional[str] = None,
        folder_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List videos for the authenticated user.

        Args:
            page_size: Number of videos per page (max 100)
            cursor: Pagination cursor
            folder_id: Filter by folder
            source: Filter by source (desktop, mobile, etc.)

        Returns:
            List of videos with pagination
        """
        params: Dict[str, Any] = {"page_size": min(page_size, 100)}
        if cursor:
            params["cursor"] = cursor
        if folder_id:
            params["folder_id"] = folder_id
        if source:
            params["source"] = source

        resp = await self.client.get("/videos", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_video(
        self,
        video_id: str,
    ) -> Dict[str, Any]:
        """Get a specific video by ID."""
        resp = await self.client.get(f"/videos/{video_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_video(
        self,
        video_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        privacy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update video metadata.

        Args:
            video_id: Video ID
            name: New video title
            description: New description
            privacy: Privacy setting (public, password, link, team, workspace)

        Returns:
            Updated video
        """
        payload: Dict[str, Any] = {}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        if privacy:
            payload["privacy"] = privacy

        resp = await self.client.patch(f"/videos/{video_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_video(
        self,
        video_id: str,
    ) -> Dict[str, Any]:
        """Delete a video (moves to trash)."""
        resp = await self.client.delete(f"/videos/{video_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_video_transcript(
        self,
        video_id: str,
    ) -> Dict[str, Any]:
        """
        Get the transcript for a video.

        Returns:
            Transcript with timestamps
        """
        resp = await self.client.get(f"/videos/{video_id}/transcript")
        resp.raise_for_status()
        return resp.json()

    async def get_video_chapters(
        self,
        video_id: str,
    ) -> Dict[str, Any]:
        """Get chapters for a video."""
        resp = await self.client.get(f"/videos/{video_id}/chapters")
        resp.raise_for_status()
        return resp.json()

    async def get_video_comments(
        self,
        video_id: str,
        page_size: int = 25,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get comments on a video."""
        params: Dict[str, Any] = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get(f"/videos/{video_id}/comments", params=params)
        resp.raise_for_status()
        return resp.json()

    async def add_video_comment(
        self,
        video_id: str,
        body: str,
        timestamp_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Add a comment to a video.

        Args:
            video_id: Video ID
            body: Comment text
            timestamp_ms: Optional timestamp in milliseconds

        Returns:
            Created comment
        """
        payload: Dict[str, Any] = {"body": body}
        if timestamp_ms is not None:
            payload["timestamp_ms"] = timestamp_ms

        resp = await self.client.post(f"/videos/{video_id}/comments", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_video_analytics(
        self,
        video_id: str,
    ) -> Dict[str, Any]:
        """Get analytics for a video."""
        resp = await self.client.get(f"/videos/{video_id}/analytics")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Folders
    # -------------------------------------------------------------------------

    async def list_folders(
        self,
        page_size: int = 25,
        cursor: Optional[str] = None,
        parent_folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List folders."""
        params: Dict[str, Any] = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        if parent_folder_id:
            params["parent_folder_id"] = parent_folder_id

        resp = await self.client.get("/folders", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_folder(
        self,
        folder_id: str,
    ) -> Dict[str, Any]:
        """Get a specific folder."""
        resp = await self.client.get(f"/folders/{folder_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_folder(
        self,
        name: str,
        parent_folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new folder."""
        payload: Dict[str, Any] = {"name": name}
        if parent_folder_id:
            payload["parent_folder_id"] = parent_folder_id

        resp = await self.client.post("/folders", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_folder(
        self,
        folder_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a folder."""
        payload: Dict[str, Any] = {}
        if name:
            payload["name"] = name

        resp = await self.client.patch(f"/folders/{folder_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_folder(
        self,
        folder_id: str,
    ) -> Dict[str, Any]:
        """Delete a folder."""
        resp = await self.client.delete(f"/folders/{folder_id}")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Workspace
    # -------------------------------------------------------------------------

    async def get_workspace(self) -> Dict[str, Any]:
        """Get workspace info."""
        resp = await self.client.get("/workspace")
        resp.raise_for_status()
        return resp.json()

    async def list_workspace_members(
        self,
        page_size: int = 25,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List workspace members."""
        params: Dict[str, Any] = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get("/workspace/members", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Embed
    # -------------------------------------------------------------------------

    async def get_embed_url(
        self,
        video_id: str,
        autoplay: bool = False,
        hide_owner: bool = False,
        hide_share: bool = False,
    ) -> Dict[str, Any]:
        """
        Get embed URL for a video.

        Args:
            video_id: Video ID
            autoplay: Start playing automatically
            hide_owner: Hide owner info
            hide_share: Hide share button

        Returns:
            Embed URL and configuration
        """
        params = {
            "autoplay": str(autoplay).lower(),
            "hide_owner": str(hide_owner).lower(),
            "hide_share": str(hide_share).lower(),
        }
        resp = await self.client.get(f"/videos/{video_id}/embed", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search_videos(
        self,
        query: str,
        page_size: int = 25,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for videos.

        Args:
            query: Search query
            page_size: Results per page
            cursor: Pagination cursor

        Returns:
            Search results
        """
        params: Dict[str, Any] = {
            "query": query,
            "page_size": page_size,
        }
        if cursor:
            params["cursor"] = cursor

        resp = await self.client.get("/videos/search", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def list_all_videos(
        self,
        max_videos: int = 500,
        folder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all videos with automatic pagination.

        Args:
            max_videos: Maximum videos to fetch
            folder_id: Optional folder filter

        Returns:
            List of all videos
        """
        all_videos: List[Dict[str, Any]] = []
        cursor = None

        while len(all_videos) < max_videos:
            result = await self.list_videos(
                page_size=100,
                cursor=cursor,
                folder_id=folder_id,
            )
            videos = result.get("videos") or []
            all_videos.extend(videos)

            cursor = result.get("next_cursor")
            if not cursor:
                break

        return all_videos[:max_videos]

    def extract_video_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract video ID from a Loom URL.

        URL formats:
        - https://www.loom.com/share/{id}
        - https://www.loom.com/embed/{id}
        """
        import re

        patterns = [
            r"loom\.com/share/([a-zA-Z0-9]+)",
            r"loom\.com/embed/([a-zA-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def format_transcript(
        self,
        transcript_data: Dict[str, Any],
    ) -> str:
        """Format transcript data into readable text."""
        segments = transcript_data.get("segments") or []
        lines = []

        for segment in segments:
            start_ms = segment.get("start_ms", 0)
            text = segment.get("text", "")

            # Convert ms to timestamp
            seconds = start_ms // 1000
            minutes = seconds // 60
            secs = seconds % 60
            timestamp = f"[{minutes:02d}:{secs:02d}]"

            lines.append(f"{timestamp} {text}")

        return "\n".join(lines)

    def extract_video_metadata(
        self,
        video: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract key metadata from a video object."""
        return {
            "id": video.get("id"),
            "name": video.get("name"),
            "description": video.get("description"),
            "duration_ms": video.get("duration_ms"),
            "duration_formatted": self._format_duration(video.get("duration_ms", 0)),
            "created_at": video.get("created_at"),
            "owner_id": video.get("owner", {}).get("id"),
            "owner_name": video.get("owner", {}).get("name"),
            "share_url": video.get("share_url"),
            "embed_url": video.get("embed_url"),
            "thumbnail_url": video.get("thumbnail_url"),
            "view_count": video.get("view_count"),
            "privacy": video.get("privacy"),
        }

    def _format_duration(self, duration_ms: int) -> str:
        """Format duration in milliseconds to human-readable string."""
        if not duration_ms:
            return "0:00"

        total_seconds = duration_ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
