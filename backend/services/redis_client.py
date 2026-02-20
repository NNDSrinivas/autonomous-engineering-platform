"""
Centralized Redis client lifecycle for health checks and shared services.

Provides a singleton async Redis client with proper connection pool management.
Prevents "transport closed" errors by ensuring clean init/shutdown lifecycle.
"""
from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

try:
    from backend.core.config import settings
except ImportError:
    from core.config import settings  # fallback for local dev


_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


async def init_redis() -> Redis:
    """
    Initialize singleton Redis client/pool (safe to call multiple times).

    Called automatically at app startup. Creates a connection pool with
    proper timeouts and health checks to prevent stale connections.
    """
    global _pool, _client

    if _client is not None:
        return _client

    _pool = ConnectionPool.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
        retry_on_timeout=True,
    )
    _client = Redis(connection_pool=_pool)
    return _client


def get_redis() -> Redis:
    """
    Get the singleton Redis client.

    Raises RuntimeError if init_redis() hasn't been called yet.
    """
    if _client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() at startup.")
    return _client


async def reset_redis() -> Redis:
    """
    Force recreate the pool/client (useful if transport got closed).

    Used by health checks for self-healing when a stale connection is detected.
    """
    global _pool, _client
    try:
        if _client is not None:
            await _client.aclose()
    finally:
        _client = None

    try:
        if _pool is not None:
            await _pool.disconnect(inuse_connections=True)
    finally:
        _pool = None

    return await init_redis()


async def close_redis() -> None:
    """
    Close Redis client and pool cleanly on shutdown.

    Called automatically at app shutdown.
    """
    global _pool, _client
    try:
        if _client is not None:
            await _client.aclose()
    finally:
        _client = None

    try:
        if _pool is not None:
            await _pool.disconnect(inuse_connections=True)
    finally:
        _pool = None
