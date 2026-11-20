import pytest
from httpx import AsyncClient, Response
from pytest import MonkeyPatch

from app.core import limits
from tests.api.test_expenses_create import expense_body, post_expense
from tests.api.test_payments import pay
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio

LIMIT_REACHED = {"code": "trip_limit_reached", "message": "Trip limit reached"}


def test_the_documented_caps() -> None:
    assert (limits.MAX_ACTIVE_MEMBERS, limits.MAX_TOTAL_MEMBERS) == (50, 200)
    assert limits.MAX_TRIPS_PER_DEVICE == 50
    assert limits.MAX_LIVE_EXPENSES == 2_000
    assert (limits.MAX_LIVE_CONTRIBUTIONS, limits.MAX_LIVE_PAYMENTS) == (1_000, 1_000)


async def trip(client: AsyncClient, **overrides: bool) -> tuple[str, list[str]]:
    detail = await create(client, **overrides)
    return detail["id"], [m["id"] for m in detail["members"]]


async def spend(client: AsyncClient, trip_id: str, ids: list[str]) -> Response:
    split = {"mode": "equal", "participants": ids}
    return await post_expense(client, trip_id, expense_body(ids[0], split))


async def contribute(client: AsyncClient, trip_id: str, ids: list[str]) -> Response:
    body = {"member_id": ids[1], "amount": 1_000, "contributed_on": "2026-11-07"}
    return await client.post(f"/trips/{trip_id}/fund/contributions", json=body)


async def test_expenses_stop_at_the_cap_and_deleting_frees_room(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_LIVE_EXPENSES", 2)
    trip_id, ids = await trip(client)
    first = await spend(client, trip_id, ids)
    assert (await spend(client, trip_id, ids)).status_code == 201

    over = await spend(client, trip_id, ids)
    await client.delete(f"/trips/{trip_id}/expenses/{first.json()['id']}")
    after_delete = await spend(client, trip_id, ids)

    assert (over.status_code, over.json()) == (409, LIMIT_REACHED)
    assert after_delete.status_code == 201


async def test_the_expense_cap_is_per_trip(client: AsyncClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_LIVE_EXPENSES", 1)
    full, full_ids = await trip(client)
    other, other_ids = await trip(client)
    await spend(client, full, full_ids)

    assert (await spend(client, full, full_ids)).status_code == 409
    assert (await spend(client, other, other_ids)).status_code == 201


async def test_contributions_stop_at_the_cap_and_deleting_frees_room(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_LIVE_CONTRIBUTIONS", 2)
    trip_id, ids = await trip(client, uses_fund=True)
    first = await contribute(client, trip_id, ids)
    assert (await contribute(client, trip_id, ids)).status_code == 201

    over = await contribute(client, trip_id, ids)
    await client.delete(f"/trips/{trip_id}/fund/contributions/{first.json()['id']}")
    after_delete = await contribute(client, trip_id, ids)

    assert (over.status_code, over.json()) == (409, LIMIT_REACHED)
    assert after_delete.status_code == 201


async def test_payments_stop_at_the_cap_and_deleting_frees_room(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_LIVE_PAYMENTS", 2)
    trip_id, ids = await trip(client)
    first = await pay(client, trip_id, ids[1], ids[0])
    assert (await pay(client, trip_id, ids[2], ids[0])).status_code == 201

    over = await pay(client, trip_id, ids[1], ids[0])
    await client.delete(f"/trips/{trip_id}/payments/{first.json()['id']}")
    after_delete = await pay(client, trip_id, ids[1], ids[0])

    assert (over.status_code, over.json()) == (409, LIMIT_REACHED)
    assert after_delete.status_code == 201


async def test_the_member_cap_follows_the_shared_constant(
    client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_ACTIVE_MEMBERS", 3)
    detail = await create(client)

    response = await client.post(f"/trips/{detail['id']}/members", json={"display_name": "Dung"})

    assert (response.status_code, response.json()["code"]) == (409, "trip_full")
