"""Two joins racing on real, committed connections (outside the rollback fixture)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.security import hash_token, new_token
from app.repositories.models import Device, Member, Trip
from app.services.devices import create_device
from app.services.errors import RuleViolation
from app.services.join import join_trip
from tests.db.factories import make_member, make_trip

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
WAITING_ON_A_LOCK = text(
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
)


@dataclass(frozen=True)
class Race:
    engine: AsyncEngine
    trip: Trip
    token: str
    binh_id: uuid.UUID
    first_id: uuid.UUID
    second_id: uuid.UUID


@pytest.fixture
async def race(db_engine: AsyncEngine) -> AsyncIterator[Race]:
    token = new_token()
    trip = make_trip(share_token_hash=hash_token(token))
    now = datetime.now(UTC)
    async with AsyncSession(db_engine, expire_on_commit=False) as setup:
        setup.add(trip)
        await setup.flush()
        an = make_member(trip, 0, display_name="An")
        binh = make_member(trip, 1, display_name="Binh")
        setup.add_all([an, binh])
        first = create_device(setup, now, timedelta(days=1))
        second = create_device(setup, now, timedelta(days=1))
        await setup.commit()
    try:
        yield Race(db_engine, trip, token, binh.id, first.device_id, second.device_id)
    finally:
        async with AsyncSession(db_engine) as cleanup:
            await cleanup.execute(delete(Trip).where(Trip.id == trip.id))
            await cleanup.execute(
                delete(Device).where(Device.id.in_([first.device_id, second.device_id]))
            )
            await cleanup.commit()


async def wait_until_blocked(engine: AsyncEngine) -> None:
    async with engine.connect() as observer:
        for _ in range(100):
            if await observer.scalar(WAITING_ON_A_LOCK):
                return
            await asyncio.sleep(0.05)
    pytest.fail("the second join never waited for the trip row lock")


async def run_race(
    race: Race, first_choice: uuid.UUID | str, second_choice: uuid.UUID | str
) -> RuleViolation | None:
    """The first join holds the trip lock while the second starts; returns the second's refusal."""
    async with (
        AsyncSession(race.engine) as first,
        AsyncSession(race.engine) as second,
    ):
        await join_trip(first, race.first_id, race.token, first_choice, NOW)
        blocked = asyncio.create_task(
            join_trip(second, race.second_id, race.token, second_choice, NOW)
        )
        await wait_until_blocked(race.engine)
        await first.commit()
        try:
            await blocked
        except RuleViolation as refusal:
            await second.rollback()
            return refusal
        await second.commit()
    return None


async def committed_members(race: Race) -> list[tuple[str, int]]:
    async with AsyncSession(race.engine) as reader:
        rows = await reader.execute(
            select(Member.display_name, Member.position)
            .where(Member.trip_id == race.trip.id)
            .order_by(Member.position)
        )
        return [(name, position) for name, position in rows]


async def test_concurrent_new_names_get_distinct_positions(race: Race) -> None:
    refusal = await run_race(race, "Dung", "Em")

    assert refusal is None
    assert (await committed_members(race))[2:] == [("Dung", 2), ("Em", 3)]


async def test_concurrent_same_name_is_taken_once(race: Race) -> None:
    refusal = await run_race(race, "Dung", "dung")

    assert refusal is not None and refusal.code == "name_taken"
    assert (await committed_members(race))[2:] == [("Dung", 2)]


async def test_concurrent_claim_of_same_member_slot_lets_only_one_through(race: Race) -> None:
    refusal = await run_race(race, race.binh_id, race.binh_id)

    assert refusal is not None and refusal.code == "member_already_joined"
