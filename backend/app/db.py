from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.model_base import Base

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "engine_create_kwargs",
    "get_session",
    "prefer_deferred_commit",
]


def engine_create_kwargs(settings: Settings) -> dict[str, object]:
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": settings.db_pool_pre_ping,
        "pool_recycle": settings.db_pool_recycle_seconds,
    }


_settings = get_settings()
engine = create_async_engine(_settings.database_url, future=True, **engine_create_kwargs(_settings))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def prefer_deferred_commit(session: AsyncSession) -> None:
    """Relax commit fsync for replayable event/projection writes on PostgreSQL."""
    if session.get_bind().dialect.name != "postgresql":
        return
    await session.execute(text("SET LOCAL synchronous_commit = OFF"))
