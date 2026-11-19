import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import ExpenseShare, Trip
from app.services import expense_edits
from app.services.errors import RuleViolation
from app.services.expenses import NewExpense
from tests.api.conftest import FrozenClock
from tests.api.test_expenses_create import created, expense_body, group_trip, parts
from tests.api.test_expenses_create_rules import INVALID_SPLIT, NOT_ACTIVE
from tests.api.test_join import join
from tests.api.test_join_preview import persist, remove_member, share_token
from tests.api.test_members import TRIP_LOCKED, lock_trip
from tests.api.test_trips import NOT_FOUND

pytestmark = pytest.mark.anyio


def everyone(ids: list[str]) -> dict[str, Any]:
    return {"mode": "equal", "participants": ids}


async def put(
    client: AsyncClient,
    trip_id: str,
    expense_id: str,
    body: dict[str, Any],
    version: int | None = None,
) -> Response:
    """PUT ``body`` against ``version``, defaulting to the expense's current version."""
    url = f"/trips/{trip_id}/expenses/{expense_id}"
    if version is None:
        current = await client.get(url)
        version = current.json()["version"] if current.status_code == 200 else 1
    return await client.put(url, json=body | {"version": version})


async def stored_shares(session: AsyncSession, expense_id: str) -> set[tuple[str, int, int]]:
    rows = await session.scalars(
        select(ExpenseShare).where(ExpenseShare.expense_id == uuid.UUID(expense_id))
    )
    return {(str(r.member_id), r.weight, r.amount) for r in rows}


async def day_totals(client: AsyncClient, trip_id: str) -> list[tuple[str, int, int]]:
    days = (await client.get(f"/trips/{trip_id}/expenses/days")).json()["days"]
    return [(d["date"], d["count"], d["total"]) for d in days]


@pytest.mark.parametrize(
    ("change", "field", "expected"),
    [
        ({"title": "  Beef  hotpot "}, "title", "Beef hotpot"),
        ({"amount": 900_000}, "amount", 900_000),
        ({"category": "transport"}, "category", "transport"),
        ({"spent_on": "2026-11-09"}, "spent_on", "2026-11-09"),
        ({"note": "Receipt attached"}, "note", "Receipt attached"),
        ({"place": "Central Market"}, "place", "Central Market"),
    ],
)
async def test_each_field_can_be_edited(
    client: AsyncClient, change: dict[str, Any], field: str, expected: Any
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids), note="old"))

    response = await put(
        client, trip_id, original["id"], expense_body(ids[0], everyone(ids), note="old") | change
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited[field] == expected
    assert edited["id"] == original["id"]
    assert edited["created_by"] == original["created_by"]
    assert edited["created_at"] == original["created_at"]
    assert (await client.get(f"/trips/{trip_id}/expenses/{original['id']}")).json() == edited


async def test_payer_can_change_to_the_fund_and_back(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client, uses_fund=True)
    original = await created(client, trip_id, expense_body(ids[1], everyone(ids)))

    to_fund = await put(client, trip_id, original["id"], expense_body(None, everyone(ids)))
    back = await put(client, trip_id, original["id"], expense_body(ids[2], everyone(ids)))

    assert (to_fund.json()["paid_by"], back.json()["paid_by"]) == (None, ids[2])


async def test_switching_from_equal_to_exact_replaces_the_share_rows(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids), amount=600_000))
    assert len(await stored_shares(session, original["id"])) == 6
    split = {"mode": "exact", "amounts": {ids[1]: 200_000, ids[3]: 400_000}}

    response = await put(
        client, trip_id, original["id"], expense_body(ids[0], split, amount=600_000)
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited["split_mode"] == "exact"
    assert parts(edited) == [(ids[1], 200_000, 200_000), (ids[3], 400_000, 400_000)]
    assert await stored_shares(session, original["id"]) == {
        (ids[1], 200_000, 200_000),
        (ids[3], 400_000, 400_000),
    }


async def test_editing_shares_and_back_to_equal_keeps_one_row_per_member(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids[:3])))
    shares = {"mode": "shares", "shares": {ids[0]: 1, ids[1]: 3}}
    await put(client, trip_id, original["id"], expense_body(ids[0], shares, amount=400_000))

    response = await put(client, trip_id, original["id"], expense_body(ids[0], everyone(ids[:2])))

    assert parts(response.json()) == [(ids[0], 1, 354_000), (ids[1], 1, 354_000)]
    assert await stored_shares(session, original["id"]) == {
        (ids[0], 1, 354_000),
        (ids[1], 1, 354_000),
    }


async def test_updated_by_is_the_editing_member_and_updated_at_moves(
    client: AsyncClient, other_client: AsyncClient, clock: FrozenClock
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await join(other_client, await share_token(client, trip_id), member_id=ids[1])
    clock.now = datetime.now(UTC) + timedelta(hours=1)

    response = await put(other_client, trip_id, original["id"], expense_body(ids[1], everyone(ids)))

    edited = response.json()
    assert (edited["created_by"], edited["updated_by"]) == (ids[0], ids[1])
    assert datetime.fromisoformat(edited["updated_at"]) == clock.now
    assert edited["created_at"] == original["created_at"]


async def test_a_removed_member_may_stay_payer_and_participant(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[5], everyone(ids)))
    await remove_member(session, trip_id, 5)

    response = await put(
        client, trip_id, original["id"], expense_body(ids[5], everyone(ids), amount=600_000)
    )

    assert response.status_code == 200
    assert response.json()["paid_by"] == ids[5]
    assert parts(response.json()) == [(m, 1, 100_000) for m in ids]


async def test_a_removed_member_cannot_be_added_even_if_on_another_expense(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    await created(client, trip_id, expense_body(ids[5], everyone(ids)))
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids[:3])))
    await remove_member(session, trip_id, 5)

    as_participant = await put(
        client, trip_id, original["id"], expense_body(ids[0], everyone([*ids[:3], ids[5]]))
    )
    as_payer = await put(client, trip_id, original["id"], expense_body(ids[5], everyone(ids[:3])))

    assert [r.status_code for r in (as_participant, as_payer)] == [409, 409]
    assert [r.json() for r in (as_participant, as_payer)] == [NOT_ACTIVE, NOT_ACTIVE]


async def test_a_removed_member_dropped_by_an_edit_cannot_come_back(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await remove_member(session, trip_id, 5)
    await put(client, trip_id, original["id"], expense_body(ids[0], everyone(ids[:5])))

    response = await put(client, trip_id, original["id"], expense_body(ids[0], everyone(ids)))

    assert (response.status_code, response.json()) == (409, NOT_ACTIVE)


async def test_ids_from_other_trips_and_unknown_ids_are_409(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await group_trip(client)
    _, foreign_ids = await group_trip(other_client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))

    responses = [
        await put(client, trip_id, original["id"], expense_body(payer, everyone(participants)))
        for payer, participants in [
            (foreign_ids[0], ids),
            (ids[0], [ids[0], foreign_ids[1]]),
            (ids[0], [ids[0], str(uuid.uuid4())]),
        ]
    ]

    assert [r.status_code for r in responses] == [409] * 3
    assert all(r.json() == NOT_ACTIVE for r in responses)


async def test_a_refused_edit_changes_nothing(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    split = {"mode": "exact", "amounts": {ids[0]: 500_000, ids[1]: 100_000}}

    no_fund = await put(client, trip_id, original["id"], expense_body(None, everyone(ids)))
    mismatch = await put(client, trip_id, original["id"], expense_body(ids[0], split))

    assert (no_fund.status_code, no_fund.json()["code"]) == (409, "no_fund")
    assert (mismatch.status_code, mismatch.json()) == (
        422,
        INVALID_SPLIT | {"difference": 108_000},
    )
    assert (await client.get(f"/trips/{trip_id}/expenses/{original['id']}")).json() == original
    assert len(await stored_shares(session, original["id"])) == 6


async def test_edits_move_the_day_totals(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    first = await created(client, trip_id, expense_body(ids[0], everyone(ids), amount=100_000))
    await created(client, trip_id, expense_body(ids[0], everyone(ids), amount=50_000))
    assert await day_totals(client, trip_id) == [("2026-11-07", 2, 150_000)]

    await put(
        client,
        trip_id,
        first["id"],
        expense_body(ids[0], everyone(ids), amount=300_000, spent_on="2026-11-08"),
    )

    assert await day_totals(client, trip_id) == [
        ("2026-11-08", 1, 300_000),
        ("2026-11-07", 1, 50_000),
    ]


async def test_unknown_foreign_and_deleted_expenses_are_the_same_404(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await group_trip(client)
    other_id, other_ids = await group_trip(other_client)
    foreign = await created(other_client, other_id, expense_body(other_ids[0], everyone(other_ids)))
    deleted = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    assert (await client.delete(f"/trips/{trip_id}/expenses/{deleted['id']}")).status_code == 204

    responses = [
        await put(client, trip_id, expense_id, expense_body(ids[0], everyone(ids)))
        for expense_id in (foreign["id"], deleted["id"], str(uuid.uuid4()))
    ]

    assert [r.status_code for r in responses] == [404] * 3
    assert all(r.json() == NOT_FOUND for r in responses)


async def test_locked_trip_cannot_be_edited(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await lock_trip(session, trip_id)

    response = await put(client, trip_id, original["id"], expense_body(ids[0], everyone(ids)))

    assert (response.status_code, response.json()) == (403, TRIP_LOCKED)


async def test_closed_trip_cannot_be_edited(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    closed = update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(closed_at=datetime.now(UTC))
    await persist(session, closed)

    response = await put(client, trip_id, original["id"], expense_body(ids[0], everyone(ids)))

    assert (response.status_code, response.json()) == (
        403,
        {"code": "trip_closed", "message": "Trip is closed"},
    )


async def test_removed_editor_is_refused_after_lock(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await remove_member(session, trip_id, 1)

    with pytest.raises(RuleViolation) as raised:
        await expense_edits.edit_expense(
            session,
            uuid.UUID(trip_id),
            uuid.UUID(original["id"]),
            uuid.UUID(ids[1]),
            NewExpense(
                title="Dinner",
                amount=100_000,
                category="food",
                spent_on=datetime(2026, 11, 7, tzinfo=UTC).date(),
                paid_by=uuid.UUID(ids[0]),
                split_mode="equal",
                weights={uuid.UUID(ids[0]): 1},
                note=None,
                place=None,
            ),
            1,
            clock.now,
        )

    assert raised.value.code == "member_not_active"
