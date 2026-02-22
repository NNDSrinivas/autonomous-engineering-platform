"""Unit tests for PreviewService - in-memory static HTML storage.

Tests:
- Store and retrieve preview content
- Delete preview by ID
- TTL expiration (1 hour default)
- Max capacity eviction (oldest first)
"""

import asyncio
import time

import pytest

from backend.services.preview.preview_service import PreviewService


@pytest.mark.asyncio
async def test_store_and_retrieve():
    """Test basic store and retrieve operations."""
    service = PreviewService(ttl_seconds=3600, max_previews=100)

    # Store HTML content
    html_content = "<h1>Test Preview</h1><p>This is a test.</p>"
    preview_id = await service.store(content=html_content, content_type="html")

    # Verify preview_id is returned
    assert preview_id is not None
    assert len(preview_id) == 36  # UUID format

    # Retrieve the preview
    preview = await service.get(preview_id)

    # Verify content matches
    assert preview is not None
    assert preview.preview_id == preview_id
    assert preview.content == html_content
    assert preview.content_type == "html"
    assert preview.created_at > 0
    assert preview.expires_at > preview.created_at


@pytest.mark.asyncio
async def test_delete_preview():
    """Test deleting a preview by ID."""
    service = PreviewService(ttl_seconds=3600, max_previews=100)

    # Store a preview
    preview_id = await service.store(content="<h1>Delete Me</h1>", content_type="html")

    # Verify it exists
    preview = await service.get(preview_id)
    assert preview is not None

    # Delete the preview
    success = await service.delete(preview_id)
    assert success is True

    # Verify it's gone
    preview = await service.get(preview_id)
    assert preview is None

    # Delete again should return False
    success = await service.delete(preview_id)
    assert success is False


@pytest.mark.asyncio
async def test_preview_expiration():
    """Test TTL expiration - preview expires after configured time."""
    # Use short TTL for testing (1 second)
    service = PreviewService(ttl_seconds=1, max_previews=100)

    # Store a preview
    preview_id = await service.store(content="<h1>Expires Soon</h1>", content_type="html")

    # Verify it exists immediately
    preview = await service.get(preview_id)
    assert preview is not None

    # Wait for expiration (1.1 seconds to account for timing)
    await asyncio.sleep(1.1)

    # Verify it's expired and deleted
    preview = await service.get(preview_id)
    assert preview is None


@pytest.mark.asyncio
async def test_max_previews_eviction_oldest():
    """Test max capacity enforcement - oldest preview is evicted when at capacity."""
    # Set max to 3 previews for easy testing
    service = PreviewService(ttl_seconds=3600, max_previews=3)

    # Store 3 previews
    id1 = await service.store(content="<h1>Preview 1</h1>", content_type="html")
    await asyncio.sleep(0.01)  # Ensure different timestamps

    id2 = await service.store(content="<h1>Preview 2</h1>", content_type="html")
    await asyncio.sleep(0.01)

    id3 = await service.store(content="<h1>Preview 3</h1>", content_type="html")

    # Verify all 3 exist
    assert await service.get(id1) is not None
    assert await service.get(id2) is not None
    assert await service.get(id3) is not None

    # Store 4th preview - should evict oldest (id1)
    id4 = await service.store(content="<h1>Preview 4</h1>", content_type="html")

    # Verify id1 is gone (oldest evicted)
    assert await service.get(id1) is None

    # Verify id2, id3, id4 still exist
    assert await service.get(id2) is not None
    assert await service.get(id3) is not None
    assert await service.get(id4) is not None
