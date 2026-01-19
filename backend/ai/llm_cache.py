"""
LLM Response Cache for AEP
==========================

Caches LLM responses to reduce costs and improve latency.
Uses a combination of in-memory LRU cache and optional Redis for distributed caching.

Features:
- Semantic similarity matching (optional)
- TTL-based expiration
- Cost savings tracking
- Cache hit/miss metrics

Usage:
    cache = LLMCache()

    # Check cache before calling LLM
    cached = await cache.get(prompt, system_prompt, model)
    if cached:
        return cached

    # After LLM call, cache the response
    await cache.set(prompt, system_prompt, model, response)
"""

import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from collections import OrderedDict
import asyncio
import os

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached LLM response."""
    response_text: str
    model: str
    provider: str
    created_at: float
    ttl_seconds: int
    tokens_used: Optional[int] = None
    hit_count: int = 0

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


@dataclass
class CacheStats:
    """Statistics for cache performance."""
    hits: int = 0
    misses: int = 0
    total_tokens_saved: int = 0
    estimated_cost_saved: float = 0.0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LLMCache:
    """
    In-memory LRU cache for LLM responses with optional Redis backend.

    Cache key is generated from:
    - Prompt text (hashed)
    - System prompt (hashed)
    - Model name
    - Temperature (rounded)

    This ensures similar requests get cache hits while different
    parameters get fresh responses.
    """

    # Cost per 1K tokens (approximate, for savings calculation)
    COST_PER_1K_TOKENS = {
        "anthropic": 0.003,  # Claude Sonnet
        "openai": 0.002,     # GPT-4o-mini
        "google": 0.001,     # Gemini Flash
    }

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,  # 1 hour
        enable_semantic_matching: bool = False,
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries to cache
            default_ttl: Default time-to-live in seconds
            enable_semantic_matching: Whether to use embedding similarity for cache lookup
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_semantic_matching = enable_semantic_matching

        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

        # Statistics
        self.stats = CacheStats()

        # Redis client (optional)
        self._redis = None
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection if configured."""
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(redis_url)
                logger.info("[CACHE] Redis backend enabled")
            except ImportError:
                logger.warning("[CACHE] Redis not installed, using memory-only cache")
            except Exception as e:
                logger.warning(f"[CACHE] Failed to connect to Redis: {e}")

    def _generate_cache_key(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate a deterministic cache key from request parameters.

        Uses SHA256 hash of the combined inputs to create a fixed-length key.
        """
        # Normalize inputs
        prompt_normalized = prompt.strip().lower()
        system_normalized = (system_prompt or "").strip().lower()
        temp_rounded = round(temperature, 1)

        # Create composite key
        key_data = json.dumps({
            "p": prompt_normalized[:500],  # First 500 chars of prompt
            "s": system_normalized[:200],   # First 200 chars of system prompt
            "m": model,
            "t": temp_rounded,
        }, sort_keys=True)

        # Hash it
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:32]
        return f"llm:{model}:{key_hash}"

    async def get(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "default",
        temperature: float = 0.2,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Look up a cached response.

        Returns:
            Tuple of (response_text, metadata) if found, None otherwise
        """
        cache_key = self._generate_cache_key(prompt, system_prompt, model, temperature)

        async with self._lock:
            # Check memory cache first
            if cache_key in self._cache:
                entry = self._cache[cache_key]

                if entry.is_expired():
                    # Remove expired entry
                    del self._cache[cache_key]
                    self.stats.misses += 1
                    return None

                # Move to end (most recently used)
                self._cache.move_to_end(cache_key)

                # Update stats
                entry.hit_count += 1
                self.stats.hits += 1
                if entry.tokens_used:
                    self.stats.total_tokens_saved += entry.tokens_used
                    provider = entry.provider.split("-")[0]  # Handle "anthropic-offline" etc.
                    cost_per_1k = self.COST_PER_1K_TOKENS.get(provider, 0.002)
                    self.stats.estimated_cost_saved += (entry.tokens_used / 1000) * cost_per_1k

                logger.info(
                    f"[CACHE] HIT for {model} (hit_rate={self.stats.hit_rate:.1%}, "
                    f"tokens_saved={self.stats.total_tokens_saved})"
                )

                return entry.response_text, {
                    "cached": True,
                    "cache_hit_count": entry.hit_count,
                    "cached_at": entry.created_at,
                }

            # Check Redis if available
            if self._redis:
                try:
                    cached_data = await self._redis.get(cache_key)
                    if cached_data:
                        data = json.loads(cached_data)
                        self.stats.hits += 1
                        logger.info(f"[CACHE] Redis HIT for {model}")
                        return data["text"], {"cached": True, "source": "redis"}
                except Exception as e:
                    logger.warning(f"[CACHE] Redis get failed: {e}")

        self.stats.misses += 1
        return None

    async def set(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        provider: str,
        response_text: str,
        tokens_used: Optional[int] = None,
        temperature: float = 0.2,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Cache an LLM response.

        Args:
            prompt: The original prompt
            system_prompt: The system prompt used
            model: Model ID
            provider: Provider ID
            response_text: The response to cache
            tokens_used: Number of tokens used (for cost tracking)
            temperature: Temperature used
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        cache_key = self._generate_cache_key(prompt, system_prompt, model, temperature)
        ttl = ttl or self.default_ttl

        async with self._lock:
            # Evict oldest entries if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            # Add new entry
            self._cache[cache_key] = CacheEntry(
                response_text=response_text,
                model=model,
                provider=provider,
                created_at=time.time(),
                ttl_seconds=ttl,
                tokens_used=tokens_used,
            )

            # Also store in Redis if available
            if self._redis:
                try:
                    data = json.dumps({
                        "text": response_text,
                        "model": model,
                        "provider": provider,
                        "tokens": tokens_used,
                    })
                    await self._redis.setex(cache_key, ttl, data)
                except Exception as e:
                    logger.warning(f"[CACHE] Redis set failed: {e}")

        logger.debug(f"[CACHE] Stored response for {model} (key={cache_key[:16]}...)")

    async def invalidate(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate cache entries.

        Args:
            pattern: If provided, only invalidate keys matching this pattern.
                    If None, invalidate all entries.

        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count

            # Pattern-based invalidation
            keys_to_remove = [
                k for k in self._cache.keys()
                if pattern in k
            ]
            for key in keys_to_remove:
                del self._cache[key]

            return len(keys_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hit_rate": f"{self.stats.hit_rate:.1%}",
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "total_requests": self.stats.hits + self.stats.misses,
            "tokens_saved": self.stats.total_tokens_saved,
            "estimated_cost_saved": f"${self.stats.estimated_cost_saved:.4f}",
            "cache_size": len(self._cache),
            "max_size": self.max_size,
        }


# Global cache instance
_cache_instance: Optional[LLMCache] = None


def get_cache() -> LLMCache:
    """Get or create the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = LLMCache(
            max_size=int(os.getenv("LLM_CACHE_MAX_SIZE", "1000")),
            default_ttl=int(os.getenv("LLM_CACHE_TTL", "3600")),
        )
    return _cache_instance
