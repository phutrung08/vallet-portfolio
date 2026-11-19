import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Member, Trip
from app.services import trips
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_trip_lock import TRIP_LOCKED
from tests.api.test_trips import DETAIL_KEYS, NOT_FOUND, create

pytestmark = pytest.mark.anyio


async def closed_at(session: AsyncSession, trip_id: str) -> datetime | None:
    statement = (
        select(Trip.closed_at)
        .where(Trip.id == uuid.UUID(trip_id))
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def test_close_marks_the_trip_closed_with_the_clock_time(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)

    response = await client.post(f"/trips/{detail['id']}/close")

    assert response.status_code == 200
    assert set(response.json()) == DETAIL_KEYS
    assert response.json() == detail | {"closed": True}
    assert await closed_at(session, detail["id"]) == clock.now
    assert (await client.get(f"/trips/{detail['id']}")).json()["closed"] is True


async def test_closing_twice_keeps_the_first_closing_time(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)
    first = await client.post(f"/trips/{detail['id']}/close")
    first_time = clock.now
    clock.advance(timedelta(hours=1))

    second = await client.post(f"/trips/{detail['id']}/close")

    assert (second.status_code, second.json()) == (200, first.json())
    assert await closed_at(session, detail["id"]) == first_time


async def test_reopen_clears_the_closing_and_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/close")

    reopened = await client.post(f"/trips/{detail['id']}/reopen")
    again = await client.post(f"/trips/{detail['id']}/reopen")

    assert (reopened.status_code, reopened.json()) == (200, detail)
    assert (again.status_code, again.json()) == (200, detail)
    assert await closed_at(session, detail["id"]) is None


async def test_the_trip_list_puts_closed_trips_last(client: AsyncClient) -> None:
    closing = await create(client, name="closing", starts_on="2027-01-01")
    open_trip = await create(client, name="open", starts_on="2026-01-01")
    await client.post(f"/trips/{closing['id']}/close")

    listed_trips = (await client.get("/trips")).json()["trips"]

    assert [(t["id"], t["closed"]) for t in listed_trips] == [
        (open_trip["id"], False),
        (closing["id"], True),
    ]


async def test_a_locked_trip_can_be_neither_closed_nor_reopened(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/close")
    await session.execute(
        update(Trip).where(Trip.id == uuid.UUID(detail["id"])).values(locked_at=datetime.now(UTC))
    )
    await session.commit()

    reopen = await client.post(f"/trips/{detail['id']}/reopen")
    other = await create(client, name="other")
    await session.execute(
        update(Trip).where(Trip.id == uuid.UUID(other["id"])).values(locked_at=datetime.now(UTC))
    )
    await session.commit()
    close = await client.post(f"/trips/{other['id']}/close")

    assert (reopen.status_code, reopen.json()) == (403, TRIP_LOCKED)
    assert (close.status_code, close.json()) == (403, TRIP_LOCKED)
    assert await closed_at(session, detail["id"]) is not None
    assert await closed_at(session, other["id"]) is None


async def test_a_member_removed_before_the_lock_cannot_close_or_reopen(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)
    trip_id, caller = uuid.UUID(detail["id"]), uuid.UUID(detail["me"])
    await session.execute(update(Member).where(Member.id == caller).values(removed_at=clock.now))
    await session.commit()

    with pytest.raises(RuleViolation) as closing:
        await trips.close_trip(session, trip_id, caller, clock.now)
    with pytest.raises(RuleViolation) as reopening:
        await trips.reopen_trip(session, trip_id, caller, clock.now)

    assert (closing.value.code, reopening.value.code) == ("member_not_active",) * 2
    assert (await client.post(f"/trips/{trip_id}/close")).status_code == 404


async def test_outsiders_get_404(client: AsyncClient, other_client: AsyncClient) -> None:
    detail = await create(client)

    responses = [
        await other_client.post(f"/trips/{detail['id']}/{action}") for action in ("close", "reopen")
    ]

    assert [(r.status_code, r.json()) for r in responses] == [(404, NOT_FOUND)] * 2
