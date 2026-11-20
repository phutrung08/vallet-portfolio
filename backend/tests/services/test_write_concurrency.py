"""Concurrent writes and snapshot isolation on real committed PostgreSQL connections."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import Response
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.deps import MemberContext
from app.api.idempotency import IdempotentWrite
from app.api.schemas.payments import PaymentOut, PaymentRequest
from app.core.db import readonly_session
from app.repositories.models import Device, Member, Payment, Trip
from app.services import expense_edits, expenses, payments
from app.services.devices import create_device
from app.services.errors import RuleViolation
from app.services.expenses import NewExpense
from tests.db.factories import make_member, make_trip
from tests.services.test_join_concurrency import wait_until_blocked

pytestmark = pytest.mark.anyio

ROUTE = "POST /trips/{trip_id}/payments"


@dataclass(frozen=True)
class Setup:
    engine: AsyncEngine
    trip: Trip
    members: list[Member]
    device_id: uuid.UUID


@pytest.fixture
async def setup(db_engine: AsyncEngine) -> AsyncIterator[Setup]:
    trip = make_trip()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        session.add(trip)
        await session.flush()
        members = [make_member(trip, 0), make_member(trip, 1)]
        session.add_all(members)
        created = create_device(session, datetime.now(UTC), timedelta(days=1))
        await session.commit()
    try:
        yield Setup(db_engine, trip, members, created.device_id)
    finally:
        async with AsyncSession(db_engine) as cleanup:
            await cleanup.execute(delete(Trip).where(Trip.id == trip.id))
            await cleanup.execute(delete(Device).where(Device.id == created.device_id))
            await cleanup.commit()


def record_once(setup: Setup, session: AsyncSession, key: uuid.UUID) -> Awaitable[PaymentOut]:
    """Run ``POST /payments`` idempotency flow against ``session``."""
    payer, payee = setup.members
    body = PaymentRequest(payer=payer.id, payee=payee.id, amount=50_000, paid_on=date(2026, 11, 8))
    caller = MemberContext(setup.device_id, setup.trip.id, payer.id)
    once = IdempotentWrite(session, caller, key, ROUTE, 201, Response())

    async def write() -> PaymentOut:
        recorded = await payments.record_payment(
            session, setup.trip.id, payer.id, body.to_new_payment(), datetime.now(UTC)
        )
        assert recorded is not None
        return PaymentOut.model_validate(recorded)

    return once.run(body, PaymentOut, write)


async def committed_payments(setup: Setup) -> int:
    async with AsyncSession(setup.engine) as reader:
        statement = select(func.count()).where(Payment.trip_id == setup.trip.id)
        return int(await reader.scalar(statement) or 0)


async def test_a_concurrent_duplicate_waits_and_replays(setup: Setup) -> None:
    key = uuid.uuid4()
    async with AsyncSession(setup.engine) as first, AsyncSession(setup.engine) as second:
        original = await record_once(setup, first, key)
        duplicate = asyncio.create_task(record_once(setup, second, key))
        await wait_until_blocked(setup.engine)
        await first.commit()
        replayed = await duplicate
        await second.commit()

    assert replayed == original
    assert await committed_payments(setup) == 1


async def test_a_concurrent_duplicate_writes_when_the_first_rolls_back(setup: Setup) -> None:
    key = uuid.uuid4()
    async with AsyncSession(setup.engine) as first, AsyncSession(setup.engine) as second:
        await record_once(setup, first, key)
        retry = asyncio.create_task(record_once(setup, second, key))
        await wait_until_blocked(setup.engine)
        await first.rollback()
        await retry
        await second.commit()

    assert await committed_payments(setup) == 1


def new_title(setup: Setup, title: str) -> NewExpense:
    ids = [m.id for m in setup.members]
    return NewExpense(
        title=title,
        amount=100_000,
        category="food",
        spent_on=date(2026, 11, 7),
        paid_by=ids[0],
        split_mode="equal",
        weights=dict.fromkeys(ids, 1),
        note=None,
        place=None,
    )


async def test_two_edits_of_the_same_version_let_exactly_one_through(setup: Setup) -> None:
    editor = setup.members[0].id
    async with AsyncSession(setup.engine) as session:
        detail = await expenses.create_expense(
            session, setup.trip.id, editor, new_title(setup, "Hotpot")
        )
        assert detail is not None
        await session.commit()

    async with AsyncSession(setup.engine) as first, AsyncSession(setup.engine) as second:
        now = datetime.now(UTC)
        won = await expense_edits.edit_expense(
            first, setup.trip.id, detail.id, editor, new_title(setup, "Beef hotpot"), 1, now
        )
        stale = asyncio.create_task(
            expense_edits.edit_expense(
                second, setup.trip.id, detail.id, editor, new_title(setup, "Chicken hotpot"), 1, now
            )
        )
        await wait_until_blocked(setup.engine)
        await first.commit()
        with pytest.raises(RuleViolation) as refusal:
            await stale
        await second.rollback()

    assert won is not None and won.version == 2
    assert refusal.value.code == "version_conflict"


async def test_readonly_session_uses_repeatable_read_snapshot_isolation(setup: Setup) -> None:
    async with readonly_session(setup.engine) as snapshot:
        iso = await snapshot.scalar(text("SHOW transaction_isolation"))
        ro = await snapshot.scalar(text("SHOW transaction_read_only"))
        count_stmt = select(func.count()).where(Payment.trip_id == setup.trip.id)
        before_count = int(await snapshot.scalar(count_stmt) or 0)

        # Commit a concurrent payment after the snapshot transaction executed its first query.
        async with AsyncSession(setup.engine) as writer:
            await payments.record_payment(
                writer,
                setup.trip.id,
                setup.members[0].id,
                payments.NewPayment(
                    setup.members[1].id, setup.members[0].id, 25_000, date(2026, 11, 8), None
                ),
                datetime.now(UTC),
            )
            await writer.commit()

        after_count = int(await snapshot.scalar(count_stmt) or 0)

    assert iso == "repeatable read"
    assert ro == "on"
    assert before_count == 0
    assert after_count == 0
    assert await committed_payments(setup) == 1
