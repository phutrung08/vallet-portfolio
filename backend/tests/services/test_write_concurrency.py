"""Concurrent expense writes on real committed connections (outside the rollback fixture)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.repositories.models import Device, Member, Trip
from app.services import expense_edits, expenses
from app.services.devices import create_device
from app.services.errors import RuleViolation
from app.services.expenses import NewExpense
from tests.db.factories import make_member, make_trip
from tests.services.test_join_concurrency import wait_until_blocked

pytestmark = pytest.mark.anyio


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
