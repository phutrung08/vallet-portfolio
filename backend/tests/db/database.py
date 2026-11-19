import os
from pathlib import Path

import anyio.to_thread
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://vallet:vallet_dev@127.0.0.1:5433/vallet_portfolio_test"
)


def database_url_for_tests() -> URL:
    return make_url(os.environ.get("VALLET_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))


def create_test_engine(url: URL, **kwargs: object) -> AsyncEngine:
    return create_async_engine(url, poolclass=NullPool, connect_args={"timeout": 5}, **kwargs)


async def create_database(url: URL) -> None:
    """Create ``url``'s database if missing; skip (or fail in CI) when the server is unreachable."""
    admin = create_test_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                name = connection.dialect.identifier_preparer.quote(str(url.database))
                await connection.execute(text(f"CREATE DATABASE {name}"))
    except OSError as error:
        reason = f"test database server unreachable at {url.host}:{url.port}: {error}"
        if os.environ.get("VALLET_REQUIRE_DB") == "1":
            pytest.fail(reason)
        pytest.skip(reason)
    finally:
        await admin.dispose()


async def run_alembic(url: URL, direction: str, revision: str) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    migrate = command.upgrade if direction == "upgrade" else command.downgrade
    await anyio.to_thread.run_sync(migrate, config, revision)
