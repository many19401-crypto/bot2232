from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import yt_dlp

from config.settings import Settings
from services.cache import Cache

from .track import Track

logger = logging.getLogger(__name__)


class ExtractorError(RuntimeError):
    pass


class MediaExtractor:
    """All yt-dlp work is isolated here and runs in a worker thread."""

    def __init__(self, settings: Settings, cache: Cache | None = None):
        self.settings = settings
        self.cache = cache
        self._base_options = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "extract_flat": False,
            "socket_timeout": 15,
            "retries": 2,
            "fragment_retries": 2,
            "cachedir": False,
        }

    @staticmethod
    def is_url(query: str) -> bool:
        parsed = urlparse(query.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def search(
        self, query: str, guild_id: int, requester_id: int, requester_name: str, limit: int = 5
    ) -> list[Track]:
        query = query.strip()
        if not query:
            raise ExtractorError("Search query is empty")
        limit = min(max(limit, 1), 10)
        cache_key = f"search:{query.lower()}:{limit}"
        cached = await self.cache.get_json(cache_key) if self.cache else None
        if cached:
            return [
                Track.from_dict(
                    {
                        **item,
                        "guild_id": guild_id,
                        "requester_id": requester_id,
                        "requester_name": requester_name,
                    }
                )
                for item in cached
            ]
        target = query if self.is_url(query) else f"ytsearch{limit}:{query}"
        try:
            data = await asyncio.to_thread(self._extract, target, True)
        except Exception as exc:
            logger.exception("Extractor search failed for %r", query)
            raise ExtractorError("The media provider could not be reached") from exc
        entries = data.get("entries") if isinstance(data, dict) else None
        raw_entries = (
            [data]
            if entries is None and isinstance(data, dict)
            else [entry for entry in entries or [] if entry]
        )
        tracks = [
            self._to_track(entry, guild_id, requester_id, requester_name)
            for entry in raw_entries[:limit]
        ]
        if self.cache and tracks:
            await self.cache.set_json(
                cache_key,
                [
                    track.to_dict() | {"guild_id": 0, "requester_id": 0, "requester_name": ""}
                    for track in tracks
                ],
                self.settings.search_cache_ttl,
            )
        return tracks

    async def resolve_stream(self, track: Track) -> str:
        """Resolve a fresh URL immediately before FFmpeg starts; never cache this URL."""
        try:
            data = await asyncio.to_thread(self._extract, track.webpage_url, False)
            if data.get("entries"):
                data = next((item for item in data["entries"] if item), data)
            url = data.get("url")
            if not url:
                raise ExtractorError("Provider returned no playable stream")
            track.stream_url = str(url)
            return track.stream_url
        except ExtractorError:
            raise
        except Exception as exc:
            logger.exception("Stream resolution failed for %s", track.webpage_url)
            raise ExtractorError("This track is unavailable right now") from exc

    async def related(
        self, track: Track, guild_id: int, requester_id: int, requester_name: str, limit: int = 5
    ) -> list[Track]:
        query = f"{track.artist} {track.title}"
        return await self.search(query, guild_id, requester_id, requester_name, limit)

    def _extract(self, target: str, search: bool) -> dict:
        options = dict(self._base_options)
        options["extract_flat"] = "in_playlist" if search else False
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info(target, download=False)
            if not isinstance(result, dict):
                raise ExtractorError("Provider returned an invalid response")
            return result

    @staticmethod
    def _to_track(entry: dict, guild_id: int, requester_id: int, requester_name: str) -> Track:
        url = entry.get("webpage_url") or entry.get("original_url") or entry.get("url")
        if not url:
            raise ExtractorError("Search result has no URL")
        return Track(
            guild_id=guild_id,
            webpage_url=str(url),
            title=str(entry.get("title") or "Untitled"),
            artist=str(entry.get("artist") or entry.get("uploader") or "Unknown artist"),
            duration=float(entry["duration"]) if entry.get("duration") is not None else None,
            thumbnail=str(entry["thumbnail"]) if entry.get("thumbnail") else None,
            source=str(entry.get("extractor_key") or entry.get("extractor") or "unknown"),
            requester_id=requester_id,
            requester_name=requester_name,
        )
