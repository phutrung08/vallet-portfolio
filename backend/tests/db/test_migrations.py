from collections.abc import AsyncIterator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import URL, Connection, text

from app.repositories.models import Base
from tests.db.database import (
    create_database,
    create_test_engine,
    database_url_for_tests,
    run_alembic,
)

pytestmark = pytest.mark.anyio

APP_TABLES = {
    "trips",
    "members",
    "expenses",
    "expense_shares",
    "fund_contributions",
    "payments",
    "bank_accounts",
    "trip_events",
    "devices",
    "memberships",
    "idempotency_keys",
}


@pytest.fixture
async def scratch_url(anyio_backend: str) -> AsyncIterator[URL]:
    url = database_url_for_tests()
    scratch = url.set(database=f"{url.database}_migrations")
    await create_database(scratch)
    yield scratch
    admin = create_test_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'DROP DATABASE "{scratch.database}" WITH (FORCE)'))
    await admin.dispose()


async def public_tables(url: URL) -> set[str]:
    engine = create_test_engine(url)
    async with engine.connect() as connection:
        rows = await connection.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = set(rows)
    await engine.dispose()
    return tables


async def table_keys(url: URL, table: str) -> dict[str, str]:
    engine = create_test_engine(url)
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = (:table)::regclass AND contype IN ('p', 'f')"
            ),
            {"table": table},
        )
        keys = {name: definition for name, definition in rows}
    await engine.dispose()
    return keys


async def index_names(url: URL, table: str) -> set[str]:
    engine = create_test_engine(url)
    async with engine.connect() as connection:
        rows = await connection.scalars(
            text("SELECT indexname FROM pg_indexes WHERE tablename = :table"), {"table": table}
        )
        names = set(rows)
    await engine.dispose()
    return names


async def table_columns(url: URL, table: str) -> set[str]:
    engine = create_test_engine(url)
    async with engine.connect() as connection:
        rows = await connection.scalars(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :table"),
            {"table": table},
        )
        columns = set(rows)
    await engine.dispose()
    return columns


def _compare_schema(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={"target_metadata": Base.metadata, "compare_type": True},
    )
    return list(compare_metadata(context, Base.metadata))


async def test_upgrade_downgrade_upgrade_round_trip(scratch_url: URL) -> None:
    await run_alembic(scratch_url, "upgrade", "head")
    assert await public_tables(scratch_url) == APP_TABLES | {"alembic_version"}

    engine = create_test_engine(scratch_url)
    async with engine.connect() as connection:
        diffs = await connection.run_sync(_compare_schema)
    await engine.dispose()
    assert diffs == []

    assert "share_token_version" in await table_columns(scratch_url, "trips")
    assert "version" in await table_columns(scratch_url, "expenses")
    assert {"pk_payments", "ix_payments_trip_id_paid_on_created_at_id"} == await index_names(
        scratch_url, "payments"
    )
    assert {"ix_devices_expires_at", "ix_devices_revoked_at"} <= await index_names(
        scratch_url, "devices"
    )
    assert "ix_idempotency_keys_created_at" in await index_names(scratch_url, "idempotency_keys")

    assert await table_keys(scratch_url, "bank_accounts") == {
        "pk_bank_accounts": "PRIMARY KEY (trip_id, member_id)",
        "fk_bank_accounts_trip_id_trips": (
            "FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE"
        ),
        "fk_bank_accounts_trip_id_member_id_members": (
            "FOREIGN KEY (trip_id, member_id) REFERENCES members(trip_id, id) "
            "DEFERRABLE INITIALLY DEFERRED"
        ),
    }
    assert await table_keys(scratch_url, "trip_events") == {
        "pk_trip_events": "PRIMARY KEY (id)",
        "fk_trip_events_trip_id_trips": (
            "FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE"
        ),
        "fk_trip_events_trip_id_actor_member_id_members": (
            "FOREIGN KEY (trip_id, actor_member_id) REFERENCES members(trip_id, id) "
            "DEFERRABLE INITIALLY DEFERRED"
        ),
        "fk_trip_events_trip_id_subject_member_id_members": (
            "FOREIGN KEY (trip_id, subject_member_id) REFERENCES members(trip_id, id) "
            "DEFERRABLE INITIALLY DEFERRED"
        ),
    }
    assert await table_keys(scratch_url, "idempotency_keys") == {
        "pk_idempotency_keys": "PRIMARY KEY (device_id, key)",
        "fk_idempotency_keys_device_id_devices": (
            "FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE"
        ),
    }

    await run_alembic(scratch_url, "downgrade", "base")
    assert await public_tables(scratch_url) == {"alembic_version"}

    await run_alembic(scratch_url, "upgrade", "head")
    assert await public_tables(scratch_url) == APP_TABLES | {"alembic_version"}
