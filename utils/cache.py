"""
Caching utilities for API responses.
Provides LRU cache with TTL-based expiration and metrics.
"""

from functools import wraps
from typing import Any, Callable, Optional
from cachetools import TTLCache
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CacheMetrics:
    """Track cache hit/miss statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# Global cache instances
_api_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)
_cache_metrics: CacheMetrics = CacheMetrics()


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a unique cache key from function name and arguments."""
    key_data = {
        "func": func_name,
        "args": [str(a) for a in args],
        "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached_api_call(ttl_seconds: Optional[int] = None):
    """
    Decorator for caching API call results.
    
    Args:
        ttl_seconds: Optional TTL override for this specific function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            global _cache_metrics
            
            # Skip caching if explicitly disabled
            if kwargs.pop("skip_cache", False):
                return await func(*args, **kwargs)
            
            cache_key = _make_cache_key(func.__name__, args, kwargs)
            
            # Check cache
            if cache_key in _api_cache:
                _cache_metrics.hits += 1
                return _api_cache[cache_key]
            
            # Cache miss - call function
            _cache_metrics.misses += 1
            result = await func(*args, **kwargs)
            
            # Store in cache
            _api_cache[cache_key] = result
            
            return result
        
        return wrapper
    return decorator


def clear_cache() -> int:
    """Clear all cached entries and return count of cleared items."""
    global _api_cache
    count = len(_api_cache)
    _api_cache.clear()
    return count


def get_cache_metrics() -> dict:
    """Get current cache metrics."""
    return {
        "hits": _cache_metrics.hits,
        "misses": _cache_metrics.misses,
        "hit_rate": f"{_cache_metrics.hit_rate:.2%}",
        "current_size": len(_api_cache),
        "max_size": _api_cache.maxsize
    }


def set_cache_ttl(ttl_seconds: int, max_size: int = 1000) -> None:
    """Reconfigure the cache with new TTL and size."""
    global _api_cache
    old_items = dict(_api_cache)
    _api_cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
    # Restore items (they'll have new TTL)
    _api_cache.update(old_items)
