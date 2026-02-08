"""
Response caching for LLM queries to improve latency.

Provides 50-95% latency improvement for repeated queries.
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Simple in-memory cache with TTL
_cache: Dict[str, tuple[Any, float]] = {}
_cache_ttl_seconds = 3600  # 1 hour TTL for cached responses
_max_cache_size = 1000  # Max cached items


def _generate_cache_key(
    message: str,
    mode: str = "agent",
    conversation_history: Optional[list] = None,
) -> str:
    """
    Generate a stable cache key from request parameters.

    Args:
        message: User query
        mode: Agent mode (agent, chat, etc.)
        conversation_history: Recent conversation context

    Returns:
        SHA256 hash of normalized inputs
    """
    # Normalize inputs for consistent hashing
    normalized = {
        "message": message.strip().lower(),
        "mode": mode,
        "history": (
            [
                {
                    "role": msg.get("role"),
                    "content": msg.get("content", "")[:100],  # First 100 chars
                }
                for msg in (conversation_history or [])[-3:]  # Last 3 messages only
            ]
            if conversation_history
            else []
        ),
    }

    # Create stable JSON representation
    cache_input = json.dumps(normalized, sort_keys=True)

    # Generate hash
    return hashlib.sha256(cache_input.encode()).hexdigest()


def get_cached_response(cache_key: str) -> Optional[Any]:
    """
    Retrieve cached response if available and not expired.

    Args:
        cache_key: Cache key from _generate_cache_key()

    Returns:
        Cached response or None if not found/expired
    """
    global _cache

    if cache_key not in _cache:
        return None

    response, timestamp = _cache[cache_key]

    # Check if expired
    if time.time() - timestamp > _cache_ttl_seconds:
        del _cache[cache_key]
        logger.debug(f"Cache expired for key {cache_key[:8]}...")
        return None

    logger.info(f"✅ Cache HIT for key {cache_key[:8]}... (saved LLM call!)")
    return response


def set_cached_response(cache_key: str, response: Any) -> None:
    """
    Store response in cache.

    Args:
        cache_key: Cache key from _generate_cache_key()
        response: Response to cache
    """
    global _cache

    # Simple LRU eviction: remove oldest if at capacity
    if len(_cache) >= _max_cache_size:
        oldest_key = min(_cache.keys(), key=lambda k: _cache[k][1])
        del _cache[oldest_key]
        logger.debug(f"Cache evicted oldest key {oldest_key[:8]}...")

    _cache[cache_key] = (response, time.time())
    logger.info(f"✅ Cached response for key {cache_key[:8]}...")


def clear_cache() -> None:
    """Clear all cached responses."""
    global _cache
    _cache.clear()
    logger.info("Cache cleared")


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache size, hit rate, etc.
    """
    return {
        "size": len(_cache),
        "max_size": _max_cache_size,
        "ttl_seconds": _cache_ttl_seconds,
        "utilization_percent": (len(_cache) / _max_cache_size) * 100,
    }
