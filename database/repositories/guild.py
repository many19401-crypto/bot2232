from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config.settings import Settings
from database.models import GuildSettings


class GuildSettingsRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession], defaults: Settings):
        self.factory = factory
        self.defaults = defaults

    async def get(self, guild_id: int) -> GuildSettings:
        async with self.factory() as session:
            item = await session.get(GuildSettings, guild_id)
            if item is None:
                item = GuildSettings(
                    guild_id=guild_id,
                    default_volume=self.defaults.default_volume,
                    max_queue_size=self.defaults.default_max_queue_size,
                    autoplay=self.defaults.default_autoplay,
                    auto_disconnect_timeout=self.defaults.default_auto_disconnect_timeout,
                )
                session.add(item)
                await session.commit()
                await session.refresh(item)
            return item

    async def update(self, guild_id: int, **values: object) -> GuildSettings:
        async with self.factory() as session:
            item = await session.get(GuildSettings, guild_id)
            if item is None:
                item = GuildSettings(guild_id=guild_id)
                session.add(item)
            for key, value in values.items():
                if not hasattr(GuildSettings, key):
                    raise ValueError(f"Unknown guild setting: {key}")
                setattr(item, key, value)
            await session.commit()
            await session.refresh(item)
            return item

    async def all(self) -> list[GuildSettings]:
        async with self.factory() as session:
            return list((await session.scalars(select(GuildSettings))).all())
