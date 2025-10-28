"""In-memory broadcaster implementation for development and testing."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List

from .base import Broadcast

logger = logging.getLogger(__name__)


class InMemoryBroadcaster(Broadcast):
    """Simple per-process broadcaster: good for dev and unit tests."""

    def __init__(self) -> None:
        self._channels: Dict[str, List[asyncio.Queue[str]]] = {}
        self._closed = False

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to all subscribers of a channel."""
        if self._closed:
            return
        queues = self._channels.get(channel)
        if not queues:
            return
        for q in list(queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # Drop message; consumers should keep up for SSE
                logger.warning(
                    f"Dropped message for channel {channel}: queue full "
                    f"(subscriber not keeping up with message rate)"
                )

    @asynccontextmanager
    async def _subscription(self, channel: str) -> AsyncIterator[asyncio.Queue[str]]:
        """Context manager for subscription lifecycle."""
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        self._channels.setdefault(channel, []).append(q)
        try:
            yield q
        finally:
            subs = self._channels.get(channel, [])
            if q in subs:
                subs.remove(q)

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        """Subscribe to a channel and yield messages."""
        async with self._subscription(channel) as q:
            while not self._closed:
                try:
                    msg = await q.get()
                    yield msg
                except asyncio.CancelledError:
                    break

    async def close(self) -> None:
        """Close the broadcaster and cleanup."""
        self._closed = True
        self._channels.clear()
