import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import anyio.to_thread
import pytest
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.jobs import cleanup as job
from app.services.cleanup import CleanupCounts
from tests.db.database import (
    create_database,
    create_test_engine,
    database_url_for_tests,
    run_alembic,
)

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)


@pytest.fixture
async def scratch_url(anyio_backend: str) -> AsyncIterator[URL]:
    """A migrated database of its own: the job commits, which the shared test database forbids."""
    url = database_url_for_tests()
    scratch = url.set(database=f"{url.database}_cleanup_job")
    await create_database(scratch)
    await run_alembic(scratch, "upgrade", "head")
    yield scratch
    admin = create_test_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'DROP DATABASE "{scratch.database}" WITH (FORCE)'))
    await admin.dispose()


@pytest.fixture
async def engine(scratch_url: URL) -> AsyncIterator[AsyncEngine]:
    engine = create_test_engine(scratch_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO devices (token_hash, expires_at) VALUES (:hash, :expires)"),
            [
                {"hash": hashlib.sha256(b"dead").digest(), "expires": NOW - timedelta(days=60)},
                {"hash": hashlib.sha256(b"live").digest(), "expires": NOW + timedelta(days=60)},
            ],
        )
    yield engine
    await engine.dispose()


async def device_count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return await connection.scalar(text("SELECT count(*) FROM devices")) or 0


async def test_run_deletes_expired_data_and_commits(engine: AsyncEngine) -> None:
    counts = await job.run(engine, NOW)

    assert counts == CleanupCounts(devices=1, idempotency_keys=0)
    assert await device_count(engine) == 1


async def test_main_exits_zero_and_logs_counts(
    engine: AsyncEngine,
    scratch_url: URL,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url=scratch_url.render_as_string(hide_password=False),
    )
    monkeypatch.setattr(job, "get_settings", lambda: settings)
    caplog.set_level("INFO", logger="app.jobs.cleanup")

    assert await anyio.to_thread.run_sync(job.main) == 0

    assert "devices=1 idempotency_keys=0" in caplog.text
    assert await device_count(engine) == 1


async def test_main_exits_nonzero_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = f"postgresql+asyncpg://nobody:{uuid.uuid4().hex}@127.0.0.1:1/none"
    monkeypatch.setattr(
        job,
        "get_settings",
        lambda: Settings(_env_file=None, environment="development", database_url=url),
    )

    assert await anyio.to_thread.run_sync(job.main) == 1
