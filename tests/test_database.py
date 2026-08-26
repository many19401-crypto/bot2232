import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config.settings import Settings
from database.models import Base
from database.repositories.guild import GuildSettingsRepository
from database.repositories.playlist import PlaylistRepository


@pytest.mark.asyncio
async def test_guild_defaults_and_playlist_duplicate_protection():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(discord_token="test")
    guild = await GuildSettingsRepository(factory, settings).get(123)
    assert guild.default_volume == settings.default_volume

    repository = PlaylistRepository(factory, max_tracks=2)
    playlist = await repository.create(42, "Roadtrip")
    await repository.add_track(
        playlist.id,
        42,
        {"url": "https://example/1", "title": "One", "artist": "Artist", "duration": 10.0},
    )
    with pytest.raises(ValueError, match="already"):
        await repository.add_track(
            playlist.id,
            42,
            {"url": "https://example/1", "title": "One", "artist": "Artist", "duration": 10.0},
        )
    await engine.dispose()
