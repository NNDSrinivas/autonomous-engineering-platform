"""Redis broadcaster implementation for production use."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from .base import Broadcast

logger = logging.getLogger(__name__)


class RedisBroadcaster(Broadcast):
    """Redis Pub/Sub broadcaster using aioredis."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._pool = None
        self._closed = False

    async def _ensure(self):
        """Ensure Redis connection pool is initialized."""
        if self._pool is None:
            try:
                import redis.asyncio as aioredis

                self._pool = aioredis.from_url(
                    self._url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=10,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                )
                logger.info(f"Redis broadcaster connected to {self._url}")
            except ImportError:
                logger.error(
                    "redis package not installed. Install with: pip install redis[hiredis]"
                )
                raise
        return self._pool

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a Redis channel."""
        if self._closed:
            return
        try:
            redis = await self._ensure()
            await redis.publish(channel, message)
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        """Subscribe to a Redis channel and yield messages."""
        redis = await self._ensure()
        pubsub = redis.pubsub()

        try:
            await pubsub.subscribe(channel)
            logger.debug(f"Subscribed to Redis channel: {channel}")

            while not self._closed:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message and message.get("type") == "message":
                        data = message.get("data")
                        if data is not None:
                            yield str(data)
                    else:
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error receiving from channel {channel}: {e}")
                    await asyncio.sleep(0.1)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                logger.debug(f"Unsubscribed from Redis channel: {channel}")
            except Exception as e:
                logger.error(f"Error unsubscribing from {channel}: {e}")

    async def close(self) -> None:
        """Close the Redis connection pool."""
        self._closed = True
        if self._pool is not None:
            try:
                await self._pool.close()
                logger.info("Redis broadcaster closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            self._pool = None
