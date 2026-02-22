"""
Preview Service - Static HTML storage and retrieval.

Phase 1: In-memory storage (MVP)
Phase 2+: Redis/S3 backend (swap implementation, same interface)
"""

import logging
import time
import uuid
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreviewContent:
    """Static preview content metadata."""

    preview_id: str
    content: str
    content_type: str  # "html", "markdown", etc.
    created_at: float
    expires_at: float


class PreviewService:
    """
    Manages static preview content storage.

    Phase 1: In-memory store (simple dict)
    Later: Swap to Redis/S3 with same interface
    """

    def __init__(self, ttl_seconds: int = 3600, max_previews: int = 100):
        self.ttl_seconds = ttl_seconds
        self.max_previews = max_previews
        self._store: Dict[str, PreviewContent] = {}
        logger.info(f"PreviewService initialized (TTL={ttl_seconds}s, max={max_previews})")

    async def store(self, content: str, content_type: str = "html") -> str:
        """
        Store preview content and return preview ID.

        Args:
            content: HTML/markdown content
            content_type: Content type ("html", "markdown")

        Returns:
            preview_id: Unique preview identifier
        """
        # Cleanup if at capacity
        if len(self._store) >= self.max_previews:
            self._cleanup_oldest()

        preview_id = str(uuid.uuid4())
        now = time.time()

        preview = PreviewContent(
            preview_id=preview_id,
            content=content,
            content_type=content_type,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )

        self._store[preview_id] = preview
        logger.info(f"Stored preview {preview_id} ({len(content)} chars)")

        return preview_id

    async def get(self, preview_id: str) -> Optional[PreviewContent]:
        """
        Retrieve preview content by ID.

        Args:
            preview_id: Preview identifier

        Returns:
            PreviewContent or None if not found/expired
        """
        preview = self._store.get(preview_id)

        if not preview:
            return None

        # Check expiration
        if time.time() > preview.expires_at:
            del self._store[preview_id]
            logger.info(f"Preview {preview_id} expired")
            return None

        return preview

    async def delete(self, preview_id: str) -> bool:
        """Delete preview by ID."""
        if preview_id in self._store:
            del self._store[preview_id]
            logger.info(f"Deleted preview {preview_id}")
            return True
        return False

    def _cleanup_oldest(self):
        """Remove oldest preview to make space."""
        if not self._store:
            return

        oldest_id = min(self._store.keys(), key=lambda k: self._store[k].created_at)
        del self._store[oldest_id]
        logger.info(f"Cleaned up oldest preview {oldest_id}")


# Global singleton instance
_preview_service: Optional[PreviewService] = None


def get_preview_service() -> PreviewService:
    """Get global PreviewService instance."""
    global _preview_service
    if _preview_service is None:
        _preview_service = PreviewService()
    return _preview_service
