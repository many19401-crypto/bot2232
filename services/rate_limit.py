from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """Per-process sliding-window limiter; Redis can be added without changing cogs."""

    def __init__(self):
        self._events: defaultdict[tuple[int, str], deque[float]] = defaultdict(deque)

    def allow(self, user_id: int, bucket: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        events = self._events[(user_id, bucket)]
        while events and now - events[0] >= window:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True
