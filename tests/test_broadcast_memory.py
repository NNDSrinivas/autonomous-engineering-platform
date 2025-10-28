"""Tests for in-memory broadcaster implementation."""

import asyncio
import pytest

from backend.infra.broadcast.memory import InMemoryBroadcaster


@pytest.mark.asyncio
async def test_inmemory_broadcast_roundtrip():
    """Test that messages published are received by subscribers."""
    bc = InMemoryBroadcaster()

    async def consumer(collected):
        async for msg in bc.subscribe("test-channel"):
            collected.append(msg)
            if len(collected) >= 2:
                break

    collected = []
    task = asyncio.create_task(consumer(collected))

    # Give subscriber time to connect
    await asyncio.sleep(0.01)

    await bc.publish("test-channel", "one")
    await bc.publish("test-channel", "two")

    # Wait for messages to be received
    await asyncio.sleep(0.05)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    assert collected == ["one", "two"]


@pytest.mark.asyncio
async def test_inmemory_multiple_subscribers():
    """Test that multiple subscribers receive the same messages."""
    bc = InMemoryBroadcaster()

    async def consumer(collected):
        async for msg in bc.subscribe("multi-channel"):
            collected.append(msg)
            if len(collected) >= 2:
                break

    collected1 = []
    collected2 = []

    task1 = asyncio.create_task(consumer(collected1))
    task2 = asyncio.create_task(consumer(collected2))

    await asyncio.sleep(0.01)

    await bc.publish("multi-channel", "msg1")
    await bc.publish("multi-channel", "msg2")

    await asyncio.sleep(0.05)

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


@pytest.mark.asyncio
async def test_inmemory_close():
    """Test that closing broadcaster stops message delivery."""
    bc = InMemoryBroadcaster()

    messages = []

    async def consumer():
        async for msg in bc.subscribe("close-channel"):
            messages.append(msg)

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0.01)

    await bc.publish("close-channel", "before-close")
    await asyncio.sleep(0.01)

    await bc.close()
    await asyncio.sleep(0.01)

    # Publishing after close should be ignored
    await bc.publish("close-channel", "after-close")
    await asyncio.sleep(0.01)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert "before-close" in messages
    assert "after-close" not in messages
