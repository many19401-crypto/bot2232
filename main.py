from __future__ import annotations

import asyncio

from bot.client import MusicBot
from config.settings import get_settings
from database.repositories.guild import GuildSettingsRepository
from database.repositories.library import FavoriteRepository, HistoryRepository
from database.repositories.playlist import PlaylistRepository
from database.session import close_database, get_session_factory, init_database
from services.cache import Cache
from utils.logger import configure_logging


async def run() -> None:
    settings = get_settings()
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
