"""Simple in-memory sliding-window rate limiter (sufficient for a single-process local demo)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import TooManyRequests


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = int(window_seconds - (now - bucket[0])) + 1
                raise TooManyRequests(f"Too many attempts. Please try again in {retry} seconds.")
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
