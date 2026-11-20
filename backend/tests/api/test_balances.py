import logging
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.repositories.models import Trip
from tests.api.conftest import CSRF_HEADERS
from tests.api.test_expenses_create import created, expense_body, group_trip
from tests.api.test_expenses_edit import everyone
from tests.api.test_expenses_read import MEMBERSHIP_QUERIES, recorded_statements
from tests.api.test_fund import contribute, contributed, fund_trip
from tests.api.test_join_preview import persist, remove_member
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio

SHEET_KEYS = {"currency", "fund", "members", "transfers"}
MEMBER_KEYS = {
    "member_id",
    "paid",
    "contributed",
    "share",
    "sent",
    "received",
    "net",
    "removed",
}
TRANSFER_KEYS = {"payer", "payee", "amount"}


async def get_balances(client: AsyncClient, trip_id: str) -> dict[str, Any]:
    response = await client.get(f"/trips/{trip_id}/balances")
    assert response.status_code == 200, response.text
    sheet: dict[str, Any] = response.json()
    return sheet


def nets(sheet: dict[str, Any]) -> list[int]:
    return [m["net"] for m in sheet["members"]]


def transfers(sheet: dict[str, Any]) -> list[tuple[str, str, int]]:
    return [(t["payer"], t["payee"], t["amount"]) for t in sheet["transfers"]]


async def test_an_empty_trip_owes_nothing(client: AsyncClient) -> None:
    detail = await create(client)
    ids = [m["id"] for m in detail["members"]]

    sheet = await get_balances(client, detail["id"])

    zeros = dict.fromkeys(MEMBER_KEYS - {"member_id", "removed"}, 0) | {"removed": False}
    assert sheet == {
        "currency": "VND",
        "fund": {"holder_id": None, "remaining": 0},
        "members": [{"member_id": i} | zeros for i in ids],
        "transfers": [],
    }


async def test_the_response_has_exactly_the_documented_keys(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    await created(client, trip_id, expense_body(ids[0], everyone(ids[:2]), amount=100_000))

    sheet = await get_balances(client, trip_id)

    assert set(sheet) == SHEET_KEYS
    assert set(sheet["fund"]) == {"holder_id", "remaining"}
    assert all(set(m) == MEMBER_KEYS for m in sheet["members"])
    assert all(set(t) == TRANSFER_KEYS for t in sheet["transfers"])
    assert [m["member_id"] for m in sheet["members"]] == ids


async def test_an_expense_paid_by_one_is_owed_by_the_others(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    await created(client, trip_id, expense_body(ids[0], everyone(ids[:3]), amount=300_000))

    sheet = await get_balances(client, trip_id)

    assert sheet["members"][0] == {
        "member_id": ids[0],
        "paid": 300_000,
        "contributed": 0,
        "share": 100_000,
        "sent": 0,
        "received": 0,
        "net": 200_000,
        "removed": False,
    }
    assert nets(sheet) == [200_000, -100_000, -100_000, 0, 0, 0]
    assert transfers(sheet) == [(ids[1], ids[0], 100_000), (ids[2], ids[0], 100_000)]


async def test_the_holder_pays_back_what_is_left_of_the_fund(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    for member in ids:
        await contributed(client, trip_id, member, 300_000)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=300_000))

    sheet = await get_balances(client, trip_id)

    assert sheet["fund"] == {"holder_id": ids[0], "remaining": 600_000}
    assert [(m["contributed"], m["share"], m["net"]) for m in sheet["members"]] == [
        (300_000, 100_000, -400_000),
        (300_000, 100_000, 200_000),
        (300_000, 100_000, 200_000),
    ]
    assert transfers(sheet) == [(ids[0], ids[1], 200_000), (ids[0], ids[2], 200_000)]


async def test_an_overdrawn_fund_is_owed_to_the_holder(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 100_000)
    await created(client, trip_id, expense_body(None, everyone(ids), amount=400_000))

    sheet = await get_balances(client, trip_id)

    assert sheet["fund"]["remaining"] == -300_000
    assert nets(sheet) == [166_666, -33_333, -133_333]
    assert sum(nets(sheet)) == 0


async def test_a_removed_member_who_still_owes_is_settled_with_the_flag(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    await created(client, trip_id, expense_body(ids[1], everyone(ids), amount=300_000))
    await remove_member(session, trip_id, 2)

    sheet = await get_balances(client, trip_id)

    assert [m["removed"] for m in sheet["members"]] == [False, False, True]
    assert nets(sheet) == [-100_000, 200_000, -100_000]
    assert transfers(sheet) == [(ids[0], ids[1], 100_000), (ids[2], ids[1], 100_000)]


async def test_a_removed_contributor_keeps_their_credit(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[2], 90_000)
    await remove_member(session, trip_id, 2)

    sheet = await get_balances(client, trip_id)

    assert sheet["members"][2]["removed"] is True
    assert nets(sheet) == [-90_000, 0, 90_000]
    assert transfers(sheet) == [(ids[0], ids[2], 90_000)]


async def test_deleted_expenses_and_contributions_do_not_count(client: AsyncClient) -> None:
    trip_id, ids = await fund_trip(client)
    kept = await created(client, trip_id, expense_body(ids[1], everyone(ids), amount=30_000))
    gone = await created(client, trip_id, expense_body(ids[1], everyone(ids), amount=60_000))
    fund_gone = await created(client, trip_id, expense_body(None, everyone(ids), amount=9_000))
    paid_in = await contributed(client, trip_id, ids[2], 12_000)
    await client.delete(f"/trips/{trip_id}/expenses/{gone['id']}")
    await client.delete(f"/trips/{trip_id}/expenses/{fund_gone['id']}")
    await client.delete(f"/trips/{trip_id}/fund/contributions/{paid_in['id']}")

    sheet = await get_balances(client, trip_id)

    assert kept["amount"] == 30_000
    assert sheet["fund"]["remaining"] == 0
    assert [(m["paid"], m["contributed"], m["share"]) for m in sheet["members"]] == [
        (0, 0, 10_000),
        (30_000, 0, 10_000),
        (0, 0, 10_000),
    ]


async def test_balances_ignore_other_trips(client: AsyncClient, other_client: AsyncClient) -> None:
    trip_id, _ = await fund_trip(client)
    other_id, other_ids = await fund_trip(other_client)
    await contributed(other_client, other_id, other_ids[1], 500_000)
    await created(other_client, other_id, expense_body(other_ids[1], everyone(other_ids)))

    sheet = await get_balances(client, trip_id)

    assert nets(sheet) == [0, 0, 0]
    assert sheet["transfers"] == []


async def test_query_count_does_not_grow_with_expenses(
    client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await fund_trip(client)
    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/balances")
        few = len(statements)
    for _ in range(6):
        await contributed(client, trip_id, ids[1], 10_000)
        await created(client, trip_id, expense_body(ids[2], everyone(ids), amount=1_000))
        await created(client, trip_id, expense_body(None, everyone(ids), amount=1_000))

    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/balances")
        many = len(statements)

    assert few == many == MEMBERSHIP_QUERIES + 4


async def test_fund_activity_without_a_holder_cannot_be_reached_through_the_api(
    client: AsyncClient,
) -> None:
    trip_id, ids = await fund_trip(client)
    assert (await contribute(client, trip_id, ids[1], 1_000)).status_code == 201

    blocked_by_contribution = await client.put(f"/trips/{trip_id}/fund", json={"holder_id": None})

    other_id, other_ids = await fund_trip(client)
    await created(client, other_id, expense_body(None, everyone(other_ids), amount=1_000))
    blocked_by_expense = await client.put(f"/trips/{other_id}/fund", json={"holder_id": None})
    assert [blocked_by_contribution.status_code, blocked_by_expense.status_code] == [409, 409]
    for checked in (trip_id, other_id):
        assert (await client.get(f"/trips/{checked}/balances")).status_code == 200


async def test_inconsistent_data_is_a_logged_generic_500(
    app: FastAPI,
    client: AsyncClient,
    session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    trip_id, ids = await fund_trip(client)
    await contributed(client, trip_id, ids[1], 1_000)
    await persist(
        session, update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(fund_holder_id=None)
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(
        transport=transport,
        base_url="https://test",
        cookies=client.cookies,
        headers=CSRF_HEADERS,
    ) as tolerant:
        response = await tolerant.get(f"/trips/{trip_id}/balances")

    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "message": "Internal server error"}
    logged = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("inconsistent" in message for message in logged)
    assert all(ids[1] not in message for message in logged)
