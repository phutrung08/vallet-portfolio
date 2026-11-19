import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import TripEvent
from app.services import fund
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_expenses_create import created, expense_body
from tests.api.test_expenses_edit import everyone
from tests.api.test_fund import FUND_KEYS, contributed, fund_trip, get_fund
from tests.api.test_fund_contributions import NOT_ACTIVE, TRIP_CLOSED, close_trip
from tests.api.test_join_preview import remove_member
from tests.api.test_members import TRIP_LOCKED, lock_trip
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio

FUND_IN_USE = {"code": "fund_in_use", "message": "Fund has contributions or fund-paid expenses"}


async def put_holder(client: AsyncClient, trip_id: str, body: Any) -> Response:
    return await client.put(f"/trips/{trip_id}/fund", json=body)


async def test_the_holder_can_change_even_with_money_in_the_fund(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 300_000)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=100_000))

    response = await put_holder(client, trip_id, {"holder_id": ids[2]})

    assert response.status_code == 200
    summary = response.json()
    assert set(summary) == FUND_KEYS
    assert (summary["holder_id"], summary["remaining"]) == (ids[2], 200_000)
    assert (await get_fund(client, trip_id))["holder_id"] == ids[2]
    detail = (await client.get(f"/trips/{trip_id}")).json()
    assert detail["fund_holder_id"] == ids[2]


async def test_a_fund_can_be_turned_on_for_a_trip_without_one(client: AsyncClient) -> None:
    detail = await create(client)
    ids = [m["id"] for m in detail["members"]]

    response = await put_holder(client, detail["id"], {"holder_id": ids[1]})

    assert (response.status_code, response.json()["holder_id"]) == (200, ids[1])


async def test_the_holder_must_be_an_active_member_of_this_trip(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    _, other_ids = await fund_trip(other_client)
    await remove_member(session, trip_id, 2)

    removed = await put_holder(client, trip_id, {"holder_id": ids[2]})
    foreign = await put_holder(client, trip_id, {"holder_id": other_ids[1]})
    unknown = await put_holder(client, trip_id, {"holder_id": str(uuid.uuid4())})

    assert [(r.status_code, r.json()) for r in (removed, foreign, unknown)] == [
        (409, NOT_ACTIVE)
    ] * 3
    assert (await get_fund(client, trip_id))["holder_id"] == ids[0]


async def test_an_empty_fund_can_be_turned_off(client: AsyncClient) -> None:
    trip_id, _ = await fund_trip(client)

    response = await put_holder(client, trip_id, {"holder_id": None})

    assert (response.status_code, response.json()["holder_id"]) == (200, None)
    assert (await client.get(f"/trips/{trip_id}")).json()["fund_holder_id"] is None


async def test_turning_off_is_blocked_by_a_contribution(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 5_000)

    response = await put_holder(client, trip_id, {"holder_id": None})

    assert (response.status_code, response.json()) == (409, FUND_IN_USE)
    assert (await get_fund(client, trip_id))["holder_id"] == ids[0]


async def test_turning_off_is_blocked_by_a_fund_paid_expense(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=5_000))

    response = await put_holder(client, trip_id, {"holder_id": None})

    assert (response.status_code, response.json()) == (409, FUND_IN_USE)


async def test_turning_off_is_allowed_once_both_are_deleted(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    contribution = await contributed(client, trip_id, ids[1], 5_000)
    expense = await created(client, trip_id, expense_body(None, everyone(ids), amount=2_000))
    assert (await put_holder(client, trip_id, {"holder_id": None})).status_code == 409

    await client.delete(f"/trips/{trip_id}/fund/contributions/{contribution['id']}")
    assert (await put_holder(client, trip_id, {"holder_id": None})).status_code == 409
    await client.delete(f"/trips/{trip_id}/expenses/{expense['id']}")
    response = await put_holder(client, trip_id, {"holder_id": None})

    assert (response.status_code, response.json()["holder_id"]) == (200, None)


async def test_locked_and_closed_trips_keep_their_holder(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    await close_trip(session, trip_id)
    closed = await put_holder(client, trip_id, {"holder_id": ids[1]})
    await lock_trip(session, trip_id)

    locked = await put_holder(client, trip_id, {"holder_id": ids[1]})

    assert (closed.status_code, closed.json()) == (403, TRIP_CLOSED)
    assert (locked.status_code, locked.json()) == (403, TRIP_LOCKED)


@pytest.mark.parametrize("body", [{}, {"holder_id": "nope"}, {"holder_id": None, "x": 1}, None])
async def test_malformed_bodies_are_rejected(client: AsyncClient, body: Any) -> None:
    trip_id, ids = await fund_trip(client)

    assert (await put_holder(client, trip_id, body)).status_code == 422
    assert (await get_fund(client, trip_id))["holder_id"] == ids[0]


async def test_a_member_holding_the_fund_still_cannot_be_removed(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    await put_holder(client, trip_id, {"holder_id": ids[1]})

    response = await client.delete(f"/trips/{trip_id}/members/{ids[1]}")

    assert (response.status_code, response.json()["code"]) == (409, "member_is_fund_holder")


async def test_changing_holder_records_fund_holder_changed_event_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)

    await put_holder(client, trip_id, {"holder_id": ids[1]})
    # Re-applying the same holder must not emit a duplicate audit event.
    await put_holder(client, trip_id, {"holder_id": ids[1]})

    events = (
        await session.scalars(
            select(TripEvent).where(
                TripEvent.trip_id == uuid.UUID(trip_id),
                TripEvent.kind == "fund_holder_changed",
            )
        )
    ).all()
    assert len(events) == 1
    assert (str(events[0].actor_member_id), str(events[0].subject_member_id)) == (ids[0], ids[1])


async def test_removed_actor_is_refused_by_set_holder_after_lock(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    trip_id, ids = await fund_trip(client)
    await remove_member(session, trip_id, 1)

    with pytest.raises(RuleViolation) as raised:
        await fund.set_holder(
            session, uuid.UUID(trip_id), uuid.UUID(ids[1]), uuid.UUID(ids[2]), clock.now
        )

    assert raised.value.code == "member_not_active"
