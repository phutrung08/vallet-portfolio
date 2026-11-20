"""Recorded payments move balances: suggested transfers shrink and eventually disappear."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_balances import get_balances, nets, transfers
from tests.api.test_balances_group_trip import enter_group_trip
from tests.api.test_expenses_create import created, expense_body, group_trip
from tests.api.test_expenses_edit import everyone
from tests.api.test_expenses_read import MEMBERSHIP_QUERIES, recorded_statements
from tests.api.test_payments import paid

pytestmark = pytest.mark.anyio


async def dinner_trip(client: AsyncClient) -> tuple[str, list[str]]:
    """An paid 300,000 for An, Binh, and Chi: Binh and Chi each owe An 100,000."""
    trip_id, ids = await group_trip(client)
    await created(client, trip_id, expense_body(ids[0], everyone(ids[:3]), amount=300_000))
    return trip_id, ids


async def test_paying_a_suggested_transfer_removes_it(client: AsyncClient) -> None:
    trip_id, ids = await dinner_trip(client)
    before = await get_balances(client, trip_id)
    assert transfers(before) == [(ids[1], ids[0], 100_000), (ids[2], ids[0], 100_000)]

    await paid(client, trip_id, ids[1], ids[0], 100_000)
    after = await get_balances(client, trip_id)

    assert transfers(after) == [(ids[2], ids[0], 100_000)]
    assert nets(after) == [100_000, 0, -100_000, 0, 0, 0]
    sent_received = [(m["sent"], m["received"]) for m in after["members"]]
    assert sent_received == [(0, 100_000), (100_000, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
    assert [(m["paid"], m["share"]) for m in after["members"]] == [
        (m["paid"], m["share"]) for m in before["members"]
    ]


async def test_a_partial_payment_shrinks_and_its_delete_restores(client: AsyncClient) -> None:
    trip_id, ids = await dinner_trip(client)
    before = await get_balances(client, trip_id)

    payment = await paid(client, trip_id, ids[2], ids[0], 30_000)
    partial = await get_balances(client, trip_id)
    await client.delete(f"/trips/{trip_id}/payments/{payment['id']}")
    restored = await get_balances(client, trip_id)

    assert transfers(partial) == [(ids[1], ids[0], 100_000), (ids[2], ids[0], 70_000)]
    assert restored == before


async def test_an_overpayment_turns_the_payer_into_a_creditor(client: AsyncClient) -> None:
    trip_id, ids = await dinner_trip(client)

    await paid(client, trip_id, ids[1], ids[0], 150_000)
    sheet = await get_balances(client, trip_id)

    assert nets(sheet)[:3] == [50_000, 50_000, -100_000]
    assert transfers(sheet) == [(ids[2], ids[0], 50_000), (ids[2], ids[1], 50_000)]


async def test_paying_every_group_trip_transfer_settles_the_trip_to_zero(
    client: AsyncClient,
) -> None:
    trip_id, _ = await enter_group_trip(client)
    suggested = transfers(await get_balances(client, trip_id))
    assert len(suggested) == 5

    for payer, payee, amount in suggested:
        await paid(client, trip_id, payer, payee, amount)
    sheet = await get_balances(client, trip_id)

    assert nets(sheet) == [0] * 6
    assert sheet["transfers"] == []
    assert all(m["paid"] + m["sent"] == m["share"] + m["received"] for m in sheet["members"])
    assert sum(m["sent"] for m in sheet["members"]) == sum(a for _, _, a in suggested)


async def test_balances_query_count_does_not_grow_with_payments(
    client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await dinner_trip(client)
    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/balances")
        few = len(statements)
    for _ in range(5):
        await paid(client, trip_id, ids[1], ids[0], 1_000)
        await paid(client, trip_id, ids[2], ids[3], 1_000)

    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/balances")
        many = len(statements)

    assert few == many == MEMBERSHIP_QUERIES + 4
