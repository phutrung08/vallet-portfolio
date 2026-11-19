from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def readonly_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield an async session inside a ``REPEATABLE READ READ ONLY`` transaction."""
    async with engine.connect() as connection:
        # Isolation and read-only options must be configured before BEGIN on asyncpg.
        await connection.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        async with (
            connection.begin(),
            AsyncSession(bind=connection, expire_on_commit=False) as session,
        ):
            yield session


async def get_readonly_session() -> AsyncIterator[AsyncSession]:
    """Yield one read-only snapshot session per request."""
    async with readonly_session(get_engine()) as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the cached engine if initialized and clear engine/session caches."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
