from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "LIVE"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


@dataclass(slots=True)
class Track:
    guild_id: int
    webpage_url: str
    title: str
    artist: str = "Unknown artist"
    duration: float | None = None
    thumbnail: str | None = None
    source: str = "unknown"
    requester_id: int = 0
    requester_name: str = "Unknown user"
    added_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    stream_url: str | None = field(default=None, repr=False)

    @property
    def duration_text(self) -> str:
        return format_duration(self.duration)

    def history_values(self) -> dict[str, object]:
        return {
            "source_url": self.webpage_url,
            "title": self.title,
            "artist": self.artist,
            "duration": self.duration,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "guild_id": self.guild_id,
            "webpage_url": self.webpage_url,
            "title": self.title,
            "artist": self.artist,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "source": self.source,
            "requester_id": self.requester_id,
            "requester_name": self.requester_name,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> Track:
        return cls(
            guild_id=int(value["guild_id"]),
            webpage_url=str(value["webpage_url"]),
            title=str(value["title"]),
            artist=str(value.get("artist") or "Unknown artist"),
            duration=float(value["duration"]) if value.get("duration") is not None else None,
            thumbnail=str(value["thumbnail"]) if value.get("thumbnail") else None,
            source=str(value.get("source") or "unknown"),
            requester_id=int(value.get("requester_id") or 0),
            requester_name=str(value.get("requester_name") or "Unknown user"),
        )
