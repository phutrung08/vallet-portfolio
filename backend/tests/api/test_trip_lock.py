import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.models import Member, Trip
from app.services import trips
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_trips import DETAIL_KEYS, NOT_FOUND, create

pytestmark = pytest.mark.anyio

TRIP_LOCKED = {"code": "trip_locked", "message": "Trip is locked"}


async def locked_at(session: AsyncSession, trip_id: str) -> datetime | None:
    statement = (
        select(Trip.locked_at)
        .where(Trip.id == uuid.UUID(trip_id))
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def is_locked(client: AsyncClient, trip_id: str) -> bool:
    locked: bool = (await client.get(f"/trips/{trip_id}")).json()["locked"]
    return locked


async def test_lock_marks_the_trip_locked_with_the_clock_time(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)

    response = await client.post(f"/trips/{detail['id']}/lock")

    assert response.status_code == 200
    assert set(response.json()) == DETAIL_KEYS
    assert response.json() == detail | {"locked": True}
    assert await locked_at(session, detail["id"]) == clock.now
    assert await is_locked(client, detail["id"]) is True


async def test_locking_twice_is_a_no_op_that_keeps_the_first_time(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)
    first = await client.post(f"/trips/{detail['id']}/lock")
    first_time = clock.now
    clock.advance(timedelta(hours=1))

    second = await client.post(f"/trips/{detail['id']}/lock")

    assert (second.status_code, second.json()) == (200, first.json())
    assert await locked_at(session, detail["id"]) == first_time


async def test_a_locked_trip_rejects_lifecycle_writes_and_keeps_reads_open(
    client: AsyncClient,
) -> None:
    detail = await create(client)
    trip_id = detail["id"]
    await client.post(f"/trips/{trip_id}/lock")
    before = (await client.get(f"/trips/{trip_id}")).json()

    close = await client.post(f"/trips/{trip_id}/close")
    reopen = await client.post(f"/trips/{trip_id}/reopen")
    rotate = await client.post(f"/trips/{trip_id}/share-link/rotate")

    assert [(r.status_code, r.json()) for r in (close, reopen, rotate)] == [(403, TRIP_LOCKED)] * 3
    assert (await client.get(f"/trips/{trip_id}")).json() == before
    assert (await client.get(f"/trips/{trip_id}/share-link")).status_code == 200


async def test_lock_keeps_the_closed_state_and_unlock_leaves_it(client: AsyncClient) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/close")

    locked = (await client.post(f"/trips/{detail['id']}/lock")).json()
    unlocked = (await client.post(f"/trips/{detail['id']}/unlock")).json()

    assert (locked["locked"], locked["closed"]) == (True, True)
    assert (unlocked["locked"], unlocked["closed"]) == (False, True)


async def test_unlock_restores_lifecycle_writes_and_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    trip_id = detail["id"]
    await client.post(f"/trips/{trip_id}/lock")

    unlocked = await client.post(f"/trips/{trip_id}/unlock")
    again = await client.post(f"/trips/{trip_id}/unlock")

    assert (unlocked.status_code, unlocked.json()["locked"]) == (200, False)
    assert (again.status_code, again.json()) == (200, unlocked.json())
    assert await locked_at(session, trip_id) is None
    assert (await client.post(f"/trips/{trip_id}/close")).status_code == 200


async def test_a_member_removed_before_the_row_lock_is_refused(
    client: AsyncClient, session: AsyncSession, settings: Settings, clock: FrozenClock
) -> None:
    detail = await create(client)
    trip_id, caller = uuid.UUID(detail["id"]), uuid.UUID(detail["me"])
    await session.execute(update(Member).where(Member.id == caller).values(removed_at=clock.now))
    await session.commit()

    with pytest.raises(RuleViolation) as locking:
        await trips.lock_trip(session, trip_id, caller, clock.now)
    with pytest.raises(RuleViolation) as unlocking:
        await trips.unlock_trip(session, trip_id, caller, clock.now)
    with pytest.raises(RuleViolation) as rotating:
        await trips.rotate_share_link(
            session, settings.share_link_key_bytes, trip_id, caller, clock.now
        )

    codes = (locking.value.code, unlocking.value.code, rotating.value.code)
    assert codes == ("member_not_active",) * 3


async def test_outsiders_get_404(client: AsyncClient, other_client: AsyncClient) -> None:
    detail = await create(client)

    responses = [
        await other_client.post(f"/trips/{detail['id']}/{action}") for action in ("lock", "unlock")
    ]

    assert [(r.status_code, r.json()) for r in responses] == [(404, NOT_FOUND)] * 2
