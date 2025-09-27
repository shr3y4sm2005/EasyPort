import time
from typing import Any, Callable, Dict, Tuple


class TTLCache:
  def __init__(self, default_ttl_seconds: int = 60, max_items: int = 1000):
    self.default_ttl = default_ttl_seconds
    self.max_items = max_items
    self.store: Dict[str, Tuple[float, Any]] = {}

  def _evict_if_needed(self):
    if len(self.store) <= self.max_items:
      return
    # Evict oldest by expiry
    oldest_key = min(self.store, key=lambda k: self.store[k][0])
    self.store.pop(oldest_key, None)

  def get(self, key: str):
    item = self.store.get(key)
    if not item:
      return None
    expires_at, value = item
    if time.time() > expires_at:
      self.store.pop(key, None)
      return None
    return value

  def set(self, key: str, value: Any, ttl_seconds: int | None = None):
    ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
    self.store[key] = (time.time() + ttl, value)
    self._evict_if_needed()

  def memoize(self, ttl_seconds: int | None = None):
    def decorator(func: Callable):
      def wrapper(*args, **kwargs):
        key = func.__name__ + str(args) + str(sorted(kwargs.items()))
        cached = self.get(key)
        if cached is not None:
          return cached
        result = func(*args, **kwargs)
        self.set(key, result, ttl_seconds)
        return result
      return wrapper
    return decorator


