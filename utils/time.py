from __future__ import annotations

import re

_TIME = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$|^(\d+(?:\.\d+)?)$")


def parse_timestamp(value: str) -> float:
    match = _TIME.fullmatch(value.strip())
    if not match:
        raise ValueError("Use seconds, M:SS or H:MM:SS")
    if match.group(4) is not None:
        return float(match.group(4))
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    if seconds >= 60 or minutes >= 60:
        raise ValueError("Invalid timestamp")
    return hours * 3600 + minutes * 60 + seconds


def progress_bar(position: float, duration: float | None, length: int = 18) -> str:
    if not duration or duration <= 0:
        return "─" * (length - 1) + "●"
    index = min(length - 1, max(0, int(position / duration * (length - 1))))
    return "─" * index + "●" + "─" * (length - index - 1)
