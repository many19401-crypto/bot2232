from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import Settings

from .models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_recycle=1800)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


async def init_database(settings: Settings) -> None:
    """Production uses Alembic; SQLite is auto-created to keep local smoke runs simple."""
    get_session_factory(settings)
    if settings.database_url.startswith("sqlite") and _engine is not None:
        async with _engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
