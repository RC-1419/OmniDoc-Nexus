import math
import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Sliding-window counters kept in memory.

    One set of counters per server process: with several workers the effective limit is roughly
    limit x workers, and counters reset when the server restarts. Enough to slow down password
    guessing and abuse of the free AI quota; it does not replace limits at a reverse proxy."""

    MAX_KEYS = 10_000

    def __init__(self, clock=time.monotonic):
        self._hits: dict[str, deque] = {}
        self._expires: dict[str, float] = {}
        self._lock = Lock()
        self._clock = clock

    def _wait(self, key: str, limit: int, window: int, now: float) -> int:
        q = self._hits.get(key)
        if not q:
            return 0
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) < limit:
            return 0
        return max(1, math.ceil(q[0] + window - now))

    def _add(self, key: str, window: int, now: float) -> None:
        self._hits.setdefault(key, deque()).append(now)
        self._expires[key] = max(self._expires.get(key, 0.0), now + window)
        if len(self._hits) > self.MAX_KEYS:  # forget keys whose window has fully passed
            for k in [k for k, exp in self._expires.items() if exp <= now]:
                self._hits.pop(k, None)
                self._expires.pop(k, None)

    def wait_time(self, key: str, limit: int, window: int) -> int:
        """Seconds until another attempt is allowed (0 = allowed now). Records nothing."""
        with self._lock:
            return self._wait(key, limit, window, self._clock())

    def record(self, key: str, window: int) -> None:
        with self._lock:
            self._add(key, window, self._clock())

    def hit(self, key: str, limit: int, window: int) -> int:
        """Record an attempt unless the limit is reached. Returns 0 if allowed, else seconds to wait."""
        with self._lock:
            now = self._clock()
            wait = self._wait(key, limit, window, now)
            if wait == 0:
                self._add(key, window, now)
            return wait
