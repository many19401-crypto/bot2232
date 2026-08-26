from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


class Cache:
    """Small Redis adapter. A cache outage never prevents playback."""

    def __init__(self, url: str | None):
        self.client = redis.from_url(url, decode_responses=True) if url else None

    async def get_json(self, key: str) -> Any | None:
        if self.client is None:
            return None
        try:
            value = await self.client.get(key)
            return json.loads(value) if value else None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        if self.client is None:
            return
        try:
            await self.client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except redis.RedisError:
            return

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
