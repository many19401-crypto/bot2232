"""Small compatibility helpers for supported Python versions."""

import datetime as dt
from enum import Enum

UTC = getattr(dt, "UTC", dt.timezone.utc)  # noqa: UP017

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - exercised only on Python 3.10

    class StrEnum(str, Enum):  # noqa: UP042
        """Backport of Python 3.11's StrEnum for Python 3.10 installations."""

        def __str__(self) -> str:
            return self.value
