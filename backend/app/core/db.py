from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_engine(url: str) -> AsyncEngine:
    """Build an async SQLAlchemy engine configured for Vallet's connection pool."""
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True,
        # Keep bound values (token hashes, later bank details) out of error messages and logs.
        hide_parameters=True,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the process-wide cached ``AsyncEngine``."""
    return create_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the cached async session factory bound to ``get_engine()``."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one async database session per request."""
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the cached engine if initialized and clear engine/session caches."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
