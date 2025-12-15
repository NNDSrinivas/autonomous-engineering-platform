"""
Performance Cache Manager

Provides in-memory caching for expensive operations to improve response times.
Includes TTL-based caching, LRU eviction, and cache statistics.
"""

import time
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL and metadata"""
    value: Any
    created_at: float
    ttl: float
    access_count: int = 0
    last_accessed: float = 0


class TTLCache:
    """Thread-safe TTL cache with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = f"{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            current_time = time.time()
            
            # Check if expired
            if current_time - entry.created_at > entry.ttl:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Update access stats and move to end (LRU)
            entry.access_count += 1
            entry.last_accessed = current_time
            self._cache.move_to_end(key)
            self._hits += 1
            
            return entry.value
    
    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store value in cache with TTL"""
        with self._lock:
            current_time = time.time()
            ttl = ttl or self.default_ttl
            
            entry = CacheEntry(
                value=value,
                created_at=current_time,
                ttl=ttl,
                last_accessed=current_time
            )
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Evict oldest if over capacity
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
    
    def clear(self) -> None:
        """Clear all cached entries"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "entries": [
                    {
                        "key": key[:16] + "..." if len(key) > 16 else key,
                        "age": time.time() - entry.created_at,
                        "ttl": entry.ttl,
                        "access_count": entry.access_count
                    }
                    for key, entry in list(self._cache.items())[:5]  # Show top 5
                ]
            }


class CacheManager:
    """Global cache manager for different types of operations"""
    
    def __init__(self):
        # Different caches for different operation types with appropriate TTLs
        self.intent_cache = TTLCache(max_size=500, default_ttl=1800)  # 30 min
        self.embedding_cache = TTLCache(max_size=200, default_ttl=3600)  # 1 hour
        self.context_cache = TTLCache(max_size=100, default_ttl=300)   # 5 min
        self.memory_cache = TTLCache(max_size=300, default_ttl=600)    # 10 min
        
    def cache_intent_classification(self, message: str, user_id: str, result: Any) -> None:
        """Cache intent classification result"""
        key = self._normalize_message_key(message, user_id)
        self.intent_cache.put(key, result, ttl=1800)  # 30 minutes
        logger.debug(f"[CACHE] Stored intent classification for key: {key[:16]}...")
    
    def get_cached_intent_classification(self, message: str, user_id: str) -> Optional[Any]:
        """Get cached intent classification result"""
        key = self._normalize_message_key(message, user_id)
        result = self.intent_cache.get(key)
        if result:
            logger.debug(f"[CACHE] Intent cache HIT for key: {key[:16]}...")
        else:
            logger.debug(f"[CACHE] Intent cache MISS for key: {key[:16]}...")
        return result
    
    def cache_embeddings(self, texts: List[str], embeddings: List[List[float]]) -> None:
        """Cache embedding results for texts"""
        for text, embedding in zip(texts, embeddings):
            key = hashlib.md5(text.encode()).hexdigest()
            self.embedding_cache.put(key, embedding, ttl=3600)  # 1 hour
    
    def get_cached_embeddings(self, texts: List[str]) -> Tuple[List[Optional[List[float]]], List[str]]:
        """Get cached embeddings, return (embeddings, uncached_texts)"""
        embeddings = []
        uncached_texts = []
        
        for text in texts:
            key = hashlib.md5(text.encode()).hexdigest()
            embedding = self.embedding_cache.get(key)
            if embedding:
                embeddings.append(embedding)
            else:
                embeddings.append(None)
                uncached_texts.append(text)
        
        return embeddings, uncached_texts
    
    def cache_context(self, context_key: str, context_data: Any, ttl: Optional[float] = None) -> None:
        """Cache expensive context operations"""
        self.context_cache.put(context_key, context_data, ttl=ttl or 300)
        logger.debug(f"[CACHE] Stored context for key: {context_key[:16]}...")
    
    def get_cached_context(self, context_key: str) -> Optional[Any]:
        """Get cached context data"""
        result = self.context_cache.get(context_key)
        if result:
            logger.debug(f"[CACHE] Context cache HIT for key: {context_key[:16]}...")
        else:
            logger.debug(f"[CACHE] Context cache MISS for key: {context_key[:16]}...")
        return result
    
    def cache_memory_search(self, query: str, user_id: str, results: Any) -> None:
        """Cache memory search results"""
        key = f"memory:{user_id}:{hashlib.md5(query.encode()).hexdigest()}"
        self.memory_cache.put(key, results, ttl=600)  # 10 minutes
    
    def get_cached_memory_search(self, query: str, user_id: str) -> Optional[Any]:
        """Get cached memory search results"""
        key = f"memory:{user_id}:{hashlib.md5(query.encode()).hexdigest()}"
        return self.memory_cache.get(key)
    
    def _normalize_message_key(self, message: str, user_id: str) -> str:
        """Create normalized cache key for message + user"""
        # Normalize message for better cache hits
        normalized = message.lower().strip()
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        # Create key
        key_data = f"{user_id}:{normalized}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def clear_all(self) -> None:
        """Clear all caches"""
        self.intent_cache.clear()
        self.embedding_cache.clear()
        self.context_cache.clear()
        self.memory_cache.clear()
        logger.info("[CACHE] Cleared all caches")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {
            "intent_cache": self.intent_cache.stats(),
            "embedding_cache": self.embedding_cache.stats(),
            "context_cache": self.context_cache.stats(),
            "memory_cache": self.memory_cache.stats(),
        }


# Global cache manager instance
cache_manager = CacheManager()