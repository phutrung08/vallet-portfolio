import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import FundContribution, Trip
from app.services import fund
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_expenses_create import created, expense_body
from tests.api.test_expenses_edit import everyone
from tests.api.test_fund import (
    CONTRIBUTION_KEYS,
    contribute,
    contributed,
    fund_trip,
    get_fund,
)
from tests.api.test_join_preview import persist, remove_member
from tests.api.test_members import TRIP_LOCKED, lock_trip
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio

NO_FUND = {"code": "no_fund", "message": "Trip has no shared fund"}
NOT_ACTIVE = {"code": "member_not_active", "message": "Member is not active in this trip"}
TRIP_CLOSED = {"code": "trip_closed", "message": "Trip is closed"}


async def close_trip(session: AsyncSession, trip_id: str) -> None:
    statement = (
        update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(closed_at=datetime.now(UTC))
    )
    await persist(session, statement)


async def test_contribution_is_recorded_for_the_member_by_the_caller(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)

    response = await contribute(client, trip_id, ids[2], 250_000, "2026-11-06")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == CONTRIBUTION_KEYS
    assert (body["member_id"], body["amount"], body["contributed_on"]) == (
        ids[2],
        250_000,
        "2026-11-06",
    )
    assert body["created_by"] == ids[0]
    assert (await get_fund(client, trip_id))["contributions"] == [body]


async def test_no_fund_is_refused(client: AsyncClient) -> None:
    detail = await create(client)

    response = await contribute(client, detail["id"], detail["members"][1]["id"], 1_000)

    assert (response.status_code, response.json()) == (409, NO_FUND)


async def test_a_removed_member_cannot_contribute(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    await remove_member(session, trip_id, 2)

    response = await contribute(client, trip_id, ids[2], 1_000)

    assert (response.status_code, response.json()) == (409, NOT_ACTIVE)


async def test_another_trips_member_is_the_same_refusal(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, _ = await fund_trip(client)
    _, other_ids = await fund_trip(other_client)

    foreign = await contribute(client, trip_id, other_ids[1], 1_000)
    unknown = await contribute(client, trip_id, str(uuid.uuid4()), 1_000)

    assert (foreign.status_code, foreign.json()) == (409, NOT_ACTIVE)
    assert (unknown.status_code, unknown.json()) == (409, NOT_ACTIVE)


async def test_locked_and_closed_trips_are_read_only(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    made = await contributed(client, trip_id, ids[1], 5_000)
    await close_trip(session, trip_id)

    closed = await contribute(client, trip_id, ids[1], 1_000)
    closed_delete = await client.delete(f"/trips/{trip_id}/fund/contributions/{made['id']}")
    await persist(session, update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(closed_at=None))
    await lock_trip(session, trip_id)
    locked = await contribute(client, trip_id, ids[1], 1_000)
    locked_delete = await client.delete(f"/trips/{trip_id}/fund/contributions/{made['id']}")

    assert (closed.status_code, closed.json()) == (403, TRIP_CLOSED)
    assert closed_delete.status_code == 403
    assert (locked.status_code, locked.json()) == (403, TRIP_LOCKED)
    assert locked_delete.status_code == 403
    assert (await get_fund(client, trip_id))["contributed"] == 5_000


@pytest.mark.parametrize("amount", [1, 10**12])
async def test_amount_bounds_are_accepted(client: AsyncClient, amount: int) -> None:
    trip_id, ids = await fund_trip(client)

    assert (await contribute(client, trip_id, ids[1], amount)).status_code == 201


@pytest.mark.parametrize("amount", [0, -5, 10**12 + 1, True, False, 1.0, 12.5, "5000", None])
async def test_invalid_amounts_are_rejected(client: AsyncClient, amount: Any) -> None:
    trip_id, ids = await fund_trip(client)

    response = await contribute(client, trip_id, ids[1], amount)

    assert response.status_code == 422
    assert response.json()["fields"] == ["body.amount"]


async def test_unknown_fields_and_bad_dates_are_rejected(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    url = f"/trips/{trip_id}/fund/contributions"
    valid = {"member_id": ids[1], "amount": 1_000, "contributed_on": "2026-11-07"}

    extra = await client.post(url, json=valid | {"created_by": ids[2]})
    bad_date = await client.post(url, json=valid | {"contributed_on": "07/11/2026"})
    missing = await client.post(url, json={"member_id": ids[1], "amount": 1_000})

    assert [r.status_code for r in (extra, bad_date, missing)] == [422, 422, 422]


async def test_delete_is_soft_and_removes_it_from_the_summary(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    made = await contributed(client, trip_id, ids[1], 5_000)

    response = await client.delete(f"/trips/{trip_id}/fund/contributions/{made['id']}")

    assert (response.status_code, response.content) == (204, b"")
    row = await session.scalar(
        select(FundContribution)
        .where(FundContribution.id == uuid.UUID(made["id"]))
        .execution_options(populate_existing=True)
    )
    assert row is not None and row.deleted_at is not None
    assert (await get_fund(client, trip_id))["contributions"] == []


async def test_delete_of_unknown_deleted_or_foreign_contribution_is_404(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await fund_trip(client)
    other_id, other_ids = await fund_trip(other_client)
    mine = await contributed(client, trip_id, ids[1], 5_000)
    theirs = await contributed(other_client, other_id, other_ids[1], 5_000)
    await client.delete(f"/trips/{trip_id}/fund/contributions/{mine['id']}")

    deleted = await client.delete(f"/trips/{trip_id}/fund/contributions/{mine['id']}")
    foreign = await client.delete(f"/trips/{trip_id}/fund/contributions/{theirs['id']}")
    unknown = await client.delete(f"/trips/{trip_id}/fund/contributions/{uuid.uuid4()}")

    assert [r.json() for r in (deleted, foreign, unknown)] == [NOT_FOUND] * 3
    assert [r.status_code for r in (deleted, foreign, unknown)] == [404] * 3
    assert (await get_fund(other_client, other_id))["contributed"] == 5_000


async def test_contributions_and_fund_expenses_are_independent_of_each_other(
    client: AsyncClient,
) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 5_000)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=2_000))

    assert (await get_fund(client, trip_id))["remaining"] == 3_000


async def test_removed_actor_is_refused_by_delete_contribution_after_lock(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    trip_id, ids = await fund_trip(client)
    made = await contributed(client, trip_id, ids[0], 5_000)
    await remove_member(session, trip_id, 1)

    with pytest.raises(RuleViolation) as raised:
        await fund.delete_contribution(
            session, uuid.UUID(trip_id), uuid.UUID(ids[1]), uuid.UUID(made["id"]), clock.now
        )

    assert raised.value.code == "member_not_active"
