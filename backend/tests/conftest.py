from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.db.database import (
    create_database,
    create_test_engine,
    database_url_for_tests,
    run_alembic,
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def db_engine(anyio_backend: str) -> AsyncIterator[AsyncEngine]:
    url = database_url_for_tests()
    await create_database(url)
    await run_alembic(url, "upgrade", "head")
    engine = create_test_engine(url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield db_session
        finally:
            await db_session.close()
            await transaction.rollback()
