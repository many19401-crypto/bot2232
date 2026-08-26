from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable

from .track import Track


class QueueError(ValueError):
    pass


class TrackQueue:
    """A bounded, priority-aware queue. Position is always 1-based for users."""

    def __init__(self, max_size: int = 100):
        if max_size < 1:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self._priority: deque[Track] = deque()
        self._items: deque[Track] = deque()

    def __len__(self) -> int:
        return len(self._priority) + len(self._items)

    def __bool__(self) -> bool:
        return bool(len(self))

    def __iter__(self):
        return iter((*self._priority, *self._items))

    def add(self, track: Track, priority: bool = False) -> int:
        if len(self) >= self.max_size:
            raise QueueError(f"Queue limit reached ({self.max_size})")
        (self._priority if priority else self._items).append(track)
        return self.position_of(track)

    def extend(self, tracks: Iterable[Track], priority: bool = False) -> int:
        values = list(tracks)
        if len(self) + len(values) > self.max_size:
            raise QueueError(f"Adding {len(values)} tracks exceeds queue limit ({self.max_size})")
        target = self._priority if priority else self._items
        target.extend(values)
        return len(self)

    def popleft(self) -> Track:
        if self._priority:
            return self._priority.popleft()
        if self._items:
            return self._items.popleft()
        raise QueueError("Queue is empty")

    def remove(self, position: int) -> Track:
        if position < 1 or position > len(self):
            raise QueueError("Queue position is out of range")
        priority_count = len(self._priority)
        values = list(self)
        removed = values.pop(position - 1)
        if position <= priority_count:
            priority_count -= 1
        self._priority = deque(values[:priority_count])
        self._items = deque(values[priority_count:])
        return removed

    def move(self, from_position: int, to_position: int) -> None:
        if not 1 <= from_position <= len(self) or not 1 <= to_position <= len(self):
            raise QueueError("Queue position is out of range")
        values = list(self)
        track = values.pop(from_position - 1)
        values.insert(to_position - 1, track)
        priority_count = len(self._priority)
        self._priority = deque(values[:priority_count])
        self._items = deque(values[priority_count:])

    def clear(self) -> list[Track]:
        old = list(self)
        self._priority.clear()
        self._items.clear()
        return old

    def shuffle(self) -> None:
        priority = list(self._priority)
        normal = list(self._items)
        rng = random.SystemRandom()
        rng.shuffle(priority)
        rng.shuffle(normal)
        self._priority = deque(priority)
        self._items = deque(normal)

    def position_of(self, track: Track) -> int:
        for index, item in enumerate(self, 1):
            if item is track:
                return index
        return -1

    def page(self, page: int, per_page: int = 10) -> tuple[list[tuple[int, Track]], int]:
        if per_page < 1:
            raise ValueError("per_page must be positive")
        pages = max(1, (len(self) + per_page - 1) // per_page)
        page = min(max(page, 1), pages)
        start = (page - 1) * per_page
        return list(enumerate(self, 1))[start : start + per_page], pages
