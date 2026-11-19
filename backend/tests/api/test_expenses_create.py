import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.balance import Expense, compute_balances
from app.repositories.models import Expense as ExpenseRow
from app.repositories.models import ExpenseShare
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio

EXPENSE_KEYS = {
    "id",
    "title",
    "amount",
    "category",
    "spent_on",
    "paid_by",
    "split_mode",
    "shares",
    "note",
    "place",
    "created_by",
    "updated_by",
    "version",
    "created_at",
    "updated_at",
}
SHARE_KEYS = {"member_id", "weight", "amount"}
GROUP_MEMBERS = ["An", "Binh", "Chi", "Dung", "Em", "Giang"]


async def group_trip(client: AsyncClient, **overrides: Any) -> tuple[str, list[str]]:
    """Create a 6-member trip and return ``(trip_id, member_ids_by_position)``."""
    detail = await create(
        client, creator_name=GROUP_MEMBERS[0], member_names=GROUP_MEMBERS[1:], **overrides
    )
    return detail["id"], [m["id"] for m in detail["members"]]


def expense_body(paid_by: str | None, split: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {
        "title": "Seafood hotpot dinner",
        "amount": 708_000,
        "category": "food",
        "spent_on": "2026-11-07",
        "paid_by": paid_by,
        "split": split,
    } | overrides


async def post_expense(client: AsyncClient, trip_id: str, body: dict[str, Any]) -> Response:
    return await client.post(f"/trips/{trip_id}/expenses", json=body)


async def created(client: AsyncClient, trip_id: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await post_expense(client, trip_id, body)
    assert response.status_code == 201, response.text
    expense: dict[str, Any] = response.json()
    return expense


def parts(expense: dict[str, Any]) -> list[tuple[str, int, int]]:
    return [(s["member_id"], s["weight"], s["amount"]) for s in expense["shares"]]


async def test_equal_split_returns_the_full_expense(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    body = expense_body(ids[1], {"mode": "equal", "participants": ids[:3]}, amount=300_001)

    expense = await created(client, trip_id, body)

    assert set(expense) == EXPENSE_KEYS
    assert all(set(s) == SHARE_KEYS for s in expense["shares"])
    assert expense["split_mode"] == "equal"
    assert parts(expense) == [(ids[0], 1, 100_001), (ids[1], 1, 100_000), (ids[2], 1, 100_000)]
    assert (expense["title"], expense["amount"], expense["category"]) == (
        "Seafood hotpot dinner",
        300_001,
        "food",
    )
    assert (expense["spent_on"], expense["paid_by"]) == ("2026-11-07", ids[1])
    assert (expense["note"], expense["place"]) == (None, None)
    assert expense["created_at"] == expense["updated_at"]
    uuid.UUID(expense["id"])


async def test_created_by_is_the_callers_member(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)

    expense = await created(
        client, trip_id, expense_body(ids[3], {"mode": "equal", "participants": ids})
    )

    assert expense["created_by"] == ids[0]


async def test_shares_split_keeps_zero_weights(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    split = {"mode": "shares", "shares": {ids[2]: 0, ids[1]: 1, ids[0]: 2}}

    expense = await created(client, trip_id, expense_body(ids[0], split, amount=300_000))

    assert expense["split_mode"] == "shares"
    assert parts(expense) == [(ids[0], 2, 200_000), (ids[1], 1, 100_000), (ids[2], 0, 0)]


async def test_percent_split(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    split = {"mode": "percent", "basis_points": {ids[0]: 3333, ids[1]: 3333, ids[2]: 3334}}

    expense = await created(client, trip_id, expense_body(ids[0], split, amount=100_000))

    assert expense["split_mode"] == "percent"
    assert parts(expense) == [
        (ids[0], 3333, 33_330),
        (ids[1], 3333, 33_330),
        (ids[2], 3334, 33_340),
    ]


async def test_exact_split(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    stated = [588_000] * 4 + [724_000] * 2
    split = {"mode": "exact", "amounts": dict(zip(ids, stated, strict=True))}

    expense = await created(client, trip_id, expense_body(ids[1], split, amount=3_800_000))

    assert expense["split_mode"] == "exact"
    assert parts(expense) == [(m, a, a) for m, a in zip(ids, stated, strict=True)]


async def test_equal_remainder_goes_to_the_lowest_positions_whatever_the_request_order(
    client: AsyncClient,
) -> None:
    trip_id, ids = await group_trip(client)
    split = {"mode": "equal", "participants": list(reversed(ids))}

    expense = await created(client, trip_id, expense_body(ids[0], split, amount=130_000))

    assert [s["member_id"] for s in expense["shares"]] == ids
    assert [s["amount"] for s in expense["shares"]] == [21_667] * 4 + [21_666] * 2


async def test_equal_over_five_of_six(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    present = [ids[0], ids[1], ids[2], ids[4], ids[5]]

    expense = await created(
        client, trip_id, expense_body(ids[4], {"mode": "equal", "participants": present})
    )

    assert parts(expense) == [(m, 1, 141_600) for m in present]


async def test_paid_from_the_fund(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client, uses_fund=True)

    expense = await created(
        client, trip_id, expense_body(None, {"mode": "equal", "participants": ids})
    )

    assert expense["paid_by"] is None


async def test_note_and_place_are_normalised(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    body = expense_body(
        ids[0],
        {"mode": "equal", "participants": ids},
        title="  Herbal  chicken 　 hotpot ",
        note="  Add extra greens\r\nand mushrooms  ",
        place="   ",
    )

    expense = await created(client, trip_id, body)

    assert expense["title"] == "Herbal chicken hotpot"
    assert (expense["note"], expense["place"]) == ("Add extra greens\nand mushrooms", None)


async def test_stored_shares_balance_to_zero(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client, uses_fund=True)
    bodies = [
        expense_body(
            ids[0], {"mode": "equal", "participants": list(reversed(ids))}, amount=130_000
        ),
        expense_body(ids[1], {"mode": "shares", "shares": {ids[2]: 3, ids[3]: 1}}, amount=99_999),
        expense_body(None, {"mode": "percent", "basis_points": {ids[4]: 7000, ids[5]: 3000}}),
        expense_body(ids[5], {"mode": "exact", "amounts": {ids[0]: 1, ids[1]: 707_999}}),
    ]
    for body in bodies:
        await created(client, trip_id, body)

    rows = (
        await session.scalars(select(ExpenseRow).where(ExpenseRow.trip_id == uuid.UUID(trip_id)))
    ).all()
    shares = (
        await session.scalars(
            select(ExpenseShare).where(ExpenseShare.trip_id == uuid.UUID(trip_id))
        )
    ).all()
    domain_expenses = [
        Expense(
            amount=row.amount,
            paid_by=None if row.paid_by_id is None else str(row.paid_by_id),
            shares={str(s.member_id): s.amount for s in shares if s.expense_id == row.id},
        )
        for row in rows
    ]
    balances = compute_balances(ids, domain_expenses, fund_holder=ids[0])

    assert len(domain_expenses) == 4
    assert sum(b.net for b in balances.values()) == 0
