from __future__ import annotations

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import Favorite, History


class FavoriteRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]):
        self.factory = factory

    async def add(self, user_id: int, values: dict[str, object]) -> bool:
        async with self.factory() as session:
            if await session.get(
                Favorite, {"user_id": user_id, "source_url": values["source_url"]}
            ):
                return False
            session.add(Favorite(user_id=user_id, **values))
            await session.commit()
            return True

    async def remove(self, user_id: int, source_url: str) -> bool:
        async with self.factory() as session:
            result = await session.execute(
                delete(Favorite).where(
                    Favorite.user_id == user_id, Favorite.source_url == source_url
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def list(self, user_id: int, limit: int = 50) -> list[Favorite]:
        async with self.factory() as session:
            return list(
                (
                    await session.scalars(
                        select(Favorite)
                        .where(Favorite.user_id == user_id)
                        .order_by(desc(Favorite.created_at))
                        .limit(limit)
                    )
                ).all()
            )


class HistoryRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]):
        self.factory = factory

    async def record(
        self, guild_id: int, user_id: int, values: dict[str, object], duration_played: float
    ) -> None:
        async with self.factory() as session:
            session.add(
                History(
                    guild_id=guild_id,
                    user_id=user_id,
                    duration_played=max(0, duration_played),
                    **values,
                )
            )
            await session.commit()

    async def recent(
        self, guild_id: int, user_id: int | None = None, limit: int = 20
    ) -> list[History]:
        async with self.factory() as session:
            query = (
                select(History)
                .where(History.guild_id == guild_id)
                .order_by(desc(History.played_at))
                .limit(limit)
            )
            if user_id is not None:
                query = query.where(History.user_id == user_id)
            return list((await session.scalars(query)).all())
