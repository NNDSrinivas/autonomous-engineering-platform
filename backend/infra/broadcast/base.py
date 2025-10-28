"""Abstract base class for broadcasting implementations."""

from __future__ import annotations

import abc
from typing import AsyncIterator, Dict


class Broadcast(abc.ABC):
    """Abstract pub/sub broadcasting interface for plan live events."""

    @abc.abstractmethod
    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a channel."""
        ...

    @abc.abstractmethod
    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        """
        Subscribe to a channel and yield messages.

        Caller must iterate/cleanup. The iterator should handle
        cancellation gracefully.
        """
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the broadcaster and cleanup resources."""
        ...


class BroadcastRegistry:
    """A simple in-process registry for broadcaster singletons."""

    _instances: Dict[str, Broadcast] = {}

    @classmethod
    def set(cls, key: str, instance: Broadcast) -> None:
        """Register a broadcaster instance."""
        prev = cls._instances.get(key)
        if prev and prev is not instance:
            # Best effort: close previous instance
            try:
                import asyncio

                asyncio.create_task(prev.close())
            except Exception:
                pass
        cls._instances[key] = instance

    @classmethod
    def get(cls, key: str) -> Broadcast | None:
        """Get a registered broadcaster instance."""
        return cls._instances.get(key)
