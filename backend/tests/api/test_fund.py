from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.api.conftest import FrozenClock
from tests.api.test_expenses_create import created, expense_body
from tests.api.test_expenses_edit import everyone
from tests.api.test_expenses_read import MEMBERSHIP_QUERIES, recorded_statements
from tests.api.test_join_preview import remove_member
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio

FUND_KEYS = {"holder_id", "contributed", "spent", "remaining", "members", "contributions"}
CONTRIBUTION_KEYS = {"id", "member_id", "amount", "contributed_on", "created_by", "created_at"}


async def fund_trip(client: AsyncClient, **overrides: Any) -> tuple[str, list[str]]:
    """Create a 3-member trip with a shared fund (first member holds it)."""
    detail = await create(client, uses_fund=True, **overrides)
    return detail["id"], [m["id"] for m in detail["members"]]


async def contribute(
    client: AsyncClient, trip_id: str, member_id: str, amount: Any, day: str = "2026-11-07"
) -> Response:
    body = {"member_id": member_id, "amount": amount, "contributed_on": day}
    return await client.post(f"/trips/{trip_id}/fund/contributions", json=body)


async def contributed(
    client: AsyncClient, trip_id: str, member_id: str, amount: int
) -> dict[str, Any]:
    response = await contribute(client, trip_id, member_id, amount)
    assert response.status_code == 201, response.text
    contribution: dict[str, Any] = response.json()
    return contribution


async def get_fund(client: AsyncClient, trip_id: str) -> dict[str, Any]:
    response = await client.get(f"/trips/{trip_id}/fund")
    assert response.status_code == 200, response.text
    summary: dict[str, Any] = response.json()
    return summary


async def test_a_trip_without_a_fund_has_an_empty_summary(client: AsyncClient) -> None:
    detail = await create(client)
    ids = [m["id"] for m in detail["members"]]

    summary = await get_fund(client, detail["id"])

    assert summary == {
        "holder_id": None,
        "contributed": 0,
        "spent": 0,
        "remaining": 0,
        "members": [{"member_id": i, "contributed": 0} for i in ids],
        "contributions": [],
    }


async def test_a_new_fund_has_its_holder_and_zeros(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)

    summary = await get_fund(client, trip_id)

    assert set(summary) == FUND_KEYS
    assert (summary["holder_id"], summary["contributed"], summary["remaining"]) == (ids[0], 0, 0)
    assert summary["members"] == [{"member_id": i, "contributed": 0} for i in ids]


async def test_summary_adds_contributions_and_subtracts_fund_paid_expenses(
    client: AsyncClient, clock: FrozenClock
) -> None:
    trip_id, ids = await fund_trip(client)
    first = await contributed(client, trip_id, ids[1], 300_000)
    clock.advance(timedelta(seconds=1))
    second = await contributed(client, trip_id, ids[0], 200_000)
    clock.advance(timedelta(seconds=1))
    third = await contributed(client, trip_id, ids[1], 100_000)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=150_000))
    await created(client, trip_id, expense_body(ids[2], everyone(ids), amount=999_000))

    summary = await get_fund(client, trip_id)

    assert (summary["contributed"], summary["spent"], summary["remaining"]) == (
        600_000,
        150_000,
        450_000,
    )
    assert summary["members"] == [
        {"member_id": ids[0], "contributed": 200_000},
        {"member_id": ids[1], "contributed": 400_000},
        {"member_id": ids[2], "contributed": 0},
    ]
    assert [c["id"] for c in summary["contributions"]] == [third["id"], second["id"], first["id"]]
    assert all(set(c) == CONTRIBUTION_KEYS for c in summary["contributions"])


async def test_remaining_goes_negative_when_the_fund_is_overdrawn(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 100_000)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=350_000))

    summary = await get_fund(client, trip_id)

    assert (summary["contributed"], summary["spent"], summary["remaining"]) == (
        100_000,
        350_000,
        -250_000,
    )


async def test_removed_members_are_listed_only_if_they_contributed(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 100_000)
    await remove_member(session, trip_id, 1)
    await remove_member(session, trip_id, 2)

    members = (await get_fund(client, trip_id))["members"]

    assert members == [
        {"member_id": ids[0], "contributed": 0},
        {"member_id": ids[1], "contributed": 100_000},
    ]


async def test_summary_reflects_deletes(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    kept = await contributed(client, trip_id, ids[1], 100_000)
    gone = await contributed(client, trip_id, ids[1], 40_000)
    spent = await created(client, trip_id, expense_body(None, everyone(ids), amount=30_000))

    await client.delete(f"/trips/{trip_id}/fund/contributions/{gone['id']}")
    await client.delete(f"/trips/{trip_id}/expenses/{spent['id']}")

    summary = await get_fund(client, trip_id)
    assert (summary["contributed"], summary["spent"], summary["remaining"]) == (100_000, 0, 100_000)
    assert [c["id"] for c in summary["contributions"]] == [kept["id"]]
    assert summary["members"][1] == {"member_id": ids[1], "contributed": 100_000}


async def test_summary_ignores_other_trips(client: AsyncClient, other_client: AsyncClient) -> None:
    trip_id, _ = await fund_trip(client)
    other_id, other_ids = await fund_trip(other_client)
    await contributed(other_client, other_id, other_ids[1], 500_000)
    await created(other_client, other_id, expense_body(None, everyone(other_ids), amount=1_000))

    summary = await get_fund(client, trip_id)

    assert (summary["contributed"], summary["spent"]) == (0, 0)


async def test_summary_query_count_does_not_grow(
    client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await fund_trip(client)
    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/fund")
        few = len(statements)
    for _ in range(5):
        await contributed(client, trip_id, ids[1], 10_000)
        await created(client, trip_id, expense_body(None, everyone(ids), amount=1_000))

    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/fund")
        many = len(statements)

    assert few == many
    assert many <= MEMBERSHIP_QUERIES + 4
