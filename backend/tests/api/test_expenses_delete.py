import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Expense, Trip
from app.services import expense_edits
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_expenses_create import created, expense_body, group_trip
from tests.api.test_expenses_edit import day_totals, everyone, put
from tests.api.test_join import join
from tests.api.test_join_preview import persist, remove_member, share_token
from tests.api.test_members import TRIP_LOCKED, lock_trip
from tests.api.test_trips import NOT_FOUND

pytestmark = pytest.mark.anyio


async def delete(client: AsyncClient, trip_id: str, expense_id: str) -> int:
    return (await client.delete(f"/trips/{trip_id}/expenses/{expense_id}")).status_code


async def test_a_deleted_expense_disappears_from_every_read(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    kept = await created(client, trip_id, expense_body(ids[0], everyone(ids), amount=50_000))
    gone = await created(client, trip_id, expense_body(ids[0], everyone(ids), amount=100_000))
    assert await day_totals(client, trip_id) == [("2026-11-07", 2, 150_000)]

    response = await client.delete(f"/trips/{trip_id}/expenses/{gone['id']}")

    assert (response.status_code, response.content) == (204, b"")
    listed = (await client.get(f"/trips/{trip_id}/expenses?day=2026-11-07")).json()["expenses"]
    assert [e["id"] for e in listed] == [kept["id"]]
    assert (await client.get(f"/trips/{trip_id}/expenses/{gone['id']}")).json() == NOT_FOUND
    assert await day_totals(client, trip_id) == [("2026-11-07", 1, 50_000)]


async def test_deleting_the_last_expense_of_a_day_removes_the_day(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    only = await created(client, trip_id, expense_body(ids[0], everyone(ids)))

    await delete(client, trip_id, only["id"])

    assert await day_totals(client, trip_id) == []


async def test_delete_is_soft_and_records_who_and_when(
    client: AsyncClient,
    other_client: AsyncClient,
    session: AsyncSession,
    clock: FrozenClock,
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await join(other_client, await share_token(client, trip_id), member_id=ids[2])
    clock.now = datetime.now(UTC) + timedelta(hours=1)

    assert await delete(other_client, trip_id, original["id"]) == 204

    row = await session.scalar(select(Expense).where(Expense.id == uuid.UUID(original["id"])))
    assert row is not None
    assert (row.deleted_at, row.updated_at) == (clock.now, clock.now)
    assert str(row.updated_by_id) == ids[2]


async def test_deleting_twice_is_404(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))

    first = await delete(client, trip_id, original["id"])
    second = await client.delete(f"/trips/{trip_id}/expenses/{original['id']}")

    assert (first, second.status_code, second.json()) == (204, 404, NOT_FOUND)


async def test_foreign_and_unknown_expenses_cannot_be_deleted(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, _ = await group_trip(client)
    other_id, other_ids = await group_trip(other_client)
    foreign = await created(other_client, other_id, expense_body(other_ids[0], everyone(other_ids)))

    responses = [
        await client.delete(f"/trips/{trip_id}/expenses/{expense_id}")
        for expense_id in (foreign["id"], str(uuid.uuid4()))
    ]

    assert [r.status_code for r in responses] == [404, 404]
    assert all(r.json() == NOT_FOUND for r in responses)
    assert (
        await other_client.get(f"/trips/{other_id}/expenses/{foreign['id']}")
    ).status_code == 200


async def test_a_foreign_expense_id_cannot_be_edited_through_this_trip(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await group_trip(client)
    other_id, other_ids = await group_trip(other_client)
    foreign = await created(other_client, other_id, expense_body(other_ids[0], everyone(other_ids)))

    response = await put(client, trip_id, foreign["id"], expense_body(ids[0], everyone(ids)))

    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    unchanged = await other_client.get(f"/trips/{other_id}/expenses/{foreign['id']}")
    assert unchanged.json() == foreign


async def test_locked_trip_cannot_delete(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await lock_trip(session, trip_id)

    response = await client.delete(f"/trips/{trip_id}/expenses/{original['id']}")

    assert (response.status_code, response.json()) == (403, TRIP_LOCKED)


async def test_closed_trip_cannot_delete(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    closed = update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(closed_at=datetime.now(UTC))
    await persist(session, closed)

    response = await client.delete(f"/trips/{trip_id}/expenses/{original['id']}")

    assert (response.status_code, response.json()) == (
        403,
        {"code": "trip_closed", "message": "Trip is closed"},
    )
    assert (await client.get(f"/trips/{trip_id}/expenses/{original['id']}")).status_code == 200


async def test_removed_deleter_is_refused_after_lock(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await remove_member(session, trip_id, 1)

    with pytest.raises(RuleViolation) as raised:
        await expense_edits.delete_expense(
            session, uuid.UUID(trip_id), uuid.UUID(original["id"]), uuid.UUID(ids[1]), clock.now
        )

    assert raised.value.code == "member_not_active"
