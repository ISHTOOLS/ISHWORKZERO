from __future__ import annotations
from collections import defaultdict, deque
from threading import RLock
from time import monotonic

class SlidingWindowRateLimiter:
    def __init__(self, limit=120, window_seconds=60):
        if limit < 1 or window_seconds <= 0: raise ValueError('invalid rate limit')
        self.limit=limit; self.window=window_seconds; self._hits=defaultdict(deque); self._lock=RLock()
    def allow(self, key: str) -> bool:
        now=monotonic()
        with self._lock:
            q=self._hits[key]
            while q and now-q[0] >= self.window: q.popleft()
            if len(q) >= self.limit: return False
            q.append(now); return True
