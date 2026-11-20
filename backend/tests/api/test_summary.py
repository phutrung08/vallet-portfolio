from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.api.test_expenses_create import created, expense_body, group_trip
from tests.api.test_expenses_edit import everyone
from tests.api.test_expenses_read import MEMBERSHIP_QUERIES, recorded_statements
from tests.api.test_join_preview import remove_member
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio

SUMMARY_KEYS = {
    "currency",
    "total",
    "expense_count",
    "active_member_count",
    "day_count",
    "per_person",
    "per_day",
    "categories",
    "payers",
    "days",
}


async def get_summary(client: AsyncClient, trip_id: str) -> dict[str, Any]:
    response = await client.get(f"/trips/{trip_id}/summary")
    assert response.status_code == 200, response.text
    report: dict[str, Any] = response.json()
    return report


async def test_empty_trip_summary_zeros_and_counts(client: AsyncClient) -> None:
    detail = await create(client, currency="USD")

    report = await get_summary(client, detail["id"])

    assert set(report) == SUMMARY_KEYS
    assert report == {
        "currency": "USD",
        "total": 0,
        "expense_count": 0,
        "active_member_count": 3,
        "day_count": 0,
        "per_person": 0,
        "per_day": 0,
        "categories": [],
        "payers": [],
        "days": [],
    }


async def test_categories_sum_to_100_percent_using_largest_remainder(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    await created(client, trip_id, expense_body(ids[0], everyone(ids), amount=100, category="food"))
    await created(
        client, trip_id, expense_body(ids[0], everyone(ids), amount=100, category="transport")
    )
    await created(
        client, trip_id, expense_body(ids[0], everyone(ids), amount=100, category="lodging")
    )

    report = await get_summary(client, trip_id)

    assert (report["total"], report["expense_count"]) == (300, 3)
    assert [
        (c["category"], c["count"], c["amount"], c["percent"]) for c in report["categories"]
    ] == [
        ("food", 1, 100, 34),
        ("lodging", 1, 100, 33),
        ("transport", 1, 100, 33),
    ]
    assert sum(c["percent"] for c in report["categories"]) == 100


async def test_summary_aggregates_payers_fund_and_excludes_removed_from_active_count(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client, uses_fund=True)
    await created(
        client,
        trip_id,
        expense_body(ids[0], everyone(ids), amount=300_000, category="food", spent_on="2026-11-07"),
    )
    await created(
        client,
        trip_id,
        expense_body(
            None, everyone(ids), amount=200_000, category="activity", spent_on="2026-11-08"
        ),
    )
    await created(
        client,
        trip_id,
        expense_body(ids[0], everyone(ids), amount=100_000, category="food", spent_on="2026-11-08"),
    )
    gone = await created(
        client, trip_id, expense_body(ids[1], everyone(ids), amount=999_000, category="shopping")
    )
    await client.delete(f"/trips/{trip_id}/expenses/{gone['id']}")
    await remove_member(session, trip_id, 5)

    report = await get_summary(client, trip_id)

    assert (
        report["total"],
        report["expense_count"],
        report["active_member_count"],
        report["day_count"],
    ) == (
        600_000,
        3,
        5,
        2,
    )
    assert (report["per_person"], report["per_day"]) == (120_000, 300_000)
    assert report["payers"] == [
        {"paid_by": ids[0], "count": 2, "amount": 400_000},
        {"paid_by": None, "count": 1, "amount": 200_000},
    ]
    assert report["days"] == [
        {"date": "2026-11-08", "count": 2, "total": 300_000},
        {"date": "2026-11-07", "count": 1, "total": 300_000},
    ]


async def test_summary_ignores_other_trips_and_keeps_constant_query_count(
    client: AsyncClient, other_client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await group_trip(client)
    other_id, other_ids = await group_trip(other_client)
    await created(other_client, other_id, expense_body(other_ids[0], everyone(other_ids)))

    with recorded_statements(db_engine) as statements:
        empty = await get_summary(client, trip_id)
        few = len(statements)

    assert empty["total"] == 0
    for idx in range(5):
        await created(
            client,
            trip_id,
            expense_body(ids[idx % len(ids)], everyone(ids), spent_on=f"2026-11-0{idx + 1}"),
        )

    with recorded_statements(db_engine) as statements:
        loaded = await get_summary(client, trip_id)
        many = len(statements)

    assert loaded["expense_count"] == 5
    assert few == many == MEMBERSHIP_QUERIES + 4
