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

    # Use event for better synchronization instead of sleep
    ready = asyncio.Event()

    async def consumer(collected):
        async for msg in bc.subscribe("test:redis:ch"):
            if not ready.is_set():
                ready.set()  # Signal that we're connected and ready
            collected.append(msg)
            if len(collected) >= 2:
                break

    collected = []
    task = asyncio.create_task(consumer(collected))

    # Wait for subscriber to be ready (or timeout after 2s)
    try:
        await asyncio.wait_for(ready.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        pass  # Continue anyway if subscriber doesn't signal

    await bc.publish("test:redis:ch", "one")
    await bc.publish("test:redis:ch", "two")

    # Wait for consumer to finish or timeout
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
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

    ready1 = asyncio.Event()
    ready2 = asyncio.Event()

    async def consumer(bc, collected, ready_event):
        async for msg in bc.subscribe("test:redis:multi"):
            if not ready_event.is_set():
                ready_event.set()
            collected.append(msg)
            if len(collected) >= 2:
                break

    collected1 = []
    collected2 = []

    task1 = asyncio.create_task(consumer(bc1, collected1, ready1))
    task2 = asyncio.create_task(consumer(bc2, collected2, ready2))

    # Wait for both subscribers to be ready
    try:
        await asyncio.wait_for(
            asyncio.gather(ready1.wait(), ready2.wait()), timeout=2.0
        )
    except asyncio.TimeoutError:
        pass

    # Publish from a third broadcaster instance
    bc_publisher = RedisBroadcaster(REDIS_URL)
    await bc_publisher.publish("test:redis:multi", "msg1")
    await bc_publisher.publish("test:redis:multi", "msg2")

    # Wait for both consumers to finish
    try:
        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=2.0)
    except asyncio.TimeoutError:
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
