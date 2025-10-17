import time
from typing import Any, Optional

class Cache:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.store = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        entry = self.store.get(key)
        if not entry:
            return None
        
        if time.time() - entry['timestamp'] > self.ttl:
            self.store.pop(key, None)
            return None
            
        return entry['value']
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp."""
        self.store[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self.store.clear()
    
    def size(self) -> int:
        """Get number of cached entries."""
        return len(self.store)