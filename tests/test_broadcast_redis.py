"""Tests for Redis broadcaster implementation."""

import os
import asyncio
import pytest

from backend.infra.broadcast.redis import RedisBroadcaster

REDIS_URL = os.getenv("REDIS_URL")

pytestmark = pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL not set")


@pytest.mark.asyncio
async def test_redis_broadcast_roundtrip():
    """Test that messages published are received by subscribers via Redis."""
    bc = RedisBroadcaster(REDIS_URL)

    async def consumer(collected):
        async for msg in bc.subscribe("test:redis:ch"):
            collected.append(msg)
            if len(collected) >= 2:
                break

    collected = []
    task = asyncio.create_task(consumer(collected))

    # Give subscriber time to connect
    await asyncio.sleep(0.1)

    await bc.publish("test:redis:ch", "one")
    await bc.publish("test:redis:ch", "two")

    # Wait for messages
    await asyncio.sleep(0.3)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    assert collected == ["one", "two"]
    await bc.close()


@pytest.mark.asyncio
async def test_redis_multiple_subscribers():
    """Test that multiple subscribers receive the same messages via Redis."""
    bc1 = RedisBroadcaster(REDIS_URL)
    bc2 = RedisBroadcaster(REDIS_URL)

    async def consumer(bc, collected):
        async for msg in bc.subscribe("test:redis:multi"):
            collected.append(msg)
            if len(collected) >= 2:
                break

    collected1 = []
    collected2 = []

    task1 = asyncio.create_task(consumer(bc1, collected1))
    task2 = asyncio.create_task(consumer(bc2, collected2))

    await asyncio.sleep(0.1)

    # Publish from a third broadcaster instance
    bc_publisher = RedisBroadcaster(REDIS_URL)
    await bc_publisher.publish("test:redis:multi", "msg1")
    await bc_publisher.publish("test:redis:multi", "msg2")

    await asyncio.sleep(0.3)

    task1.cancel()
    task2.cancel()

    try:
        await task1
    except asyncio.CancelledError:
        pass

    try:
        await task2
    except asyncio.CancelledError:
        pass

    assert collected1 == ["msg1", "msg2"]
    assert collected2 == ["msg1", "msg2"]

    await bc1.close()
    await bc2.close()
    await bc_publisher.close()
