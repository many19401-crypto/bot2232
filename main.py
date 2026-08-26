from __future__ import annotations

import asyncio
import sys

from pydantic import ValidationError

from bot.client import MusicBot
from config.settings import get_settings
from database.repositories.guild import GuildSettingsRepository
from database.repositories.library import FavoriteRepository, HistoryRepository
from database.repositories.playlist import PlaylistRepository
from database.session import close_database, get_session_factory, init_database
from services.cache import Cache
from utils.logger import configure_logging


async def run() -> None:
    try:
        settings = get_settings()
    except ValidationError as exc:
        print(
            "Configuration error: DISCORD_TOKEN is missing or invalid. "
            "Copy .env.example to .env and set DISCORD_TOKEN.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    configure_logging(settings.log_level)
    await init_database(settings)
    factory = get_session_factory(settings)
    cache = Cache(settings.redis_url)
    bot = MusicBot(
        settings,
        GuildSettingsRepository(factory, settings),
        PlaylistRepository(factory, settings.max_playlist_tracks),
        FavoriteRepository(factory),
        HistoryRepository(factory),
        cache,
    )
    try:
        await bot.start(settings.discord_token)
    finally:
        await bot.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(run())
