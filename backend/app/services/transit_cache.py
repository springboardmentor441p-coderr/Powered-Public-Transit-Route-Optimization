"""
RouteRanker: Transit In-Memory Cache Service
Provides thread-safe TTL caching for real-time CTA API responses to respect rate limits.
"""

import time
import threading
from typing import Any, Optional, Tuple

class TransitCache:
    def __init__(self, default_ttl_seconds: int = 30):
        self._cache = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl_seconds
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, expire_at, updated_at = self._cache[key]
                if time.time() < expire_at:
                    self.hits += 1
                    return value, updated_at
                else:
                    del self._cache[key]
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> str:
        ttl = ttl if ttl is not None else self.default_ttl
        now = time.time()
        expire_at = now + ttl
        updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        with self._lock:
            self._cache[key] = (value, expire_at, updated_at)
        return updated_at

    def clear(self):
        with self._lock:
            self._cache.clear()

# Global singleton cache
global_transit_cache = TransitCache(default_ttl_seconds=30)

