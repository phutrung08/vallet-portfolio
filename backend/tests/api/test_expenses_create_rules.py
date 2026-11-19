import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Trip
from app.services import expenses
from app.services.errors import RuleViolation
from app.services.expenses import NewExpense
from tests.api.test_expenses_create import expense_body, group_trip, post_expense
from tests.api.test_join_preview import persist, remove_member
from tests.api.test_members import TRIP_LOCKED, lock_trip

pytestmark = pytest.mark.anyio

NOT_ACTIVE = {"code": "member_not_active", "message": "Member is not active in this trip"}
INVALID_SPLIT = {"code": "invalid_split", "message": "Split does not add up"}


async def test_fund_payment_without_a_fund_is_409(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)

    response = await post_expense(
        client, trip_id, expense_body(None, {"mode": "equal", "participants": ids})
    )

    assert (response.status_code, response.json()) == (
        409,
        {"code": "no_fund", "message": "Trip has no shared fund"},
    )


@pytest.mark.parametrize("role", ["payer", "participant"])
async def test_removed_foreign_and_unknown_members_get_one_409(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, role: str
) -> None:
    trip_id, ids = await group_trip(client)
    _, foreign_ids = await group_trip(other_client)
    await remove_member(session, trip_id, 5)

    responses = []
    for outsider in (ids[5], foreign_ids[1], str(uuid.uuid4())):
        payer, participants = (
            (outsider, ids[:2]) if role == "payer" else (ids[0], [ids[0], outsider])
        )
        body = expense_body(payer, {"mode": "equal", "participants": participants})
        responses.append(await post_expense(client, trip_id, body))

    assert [r.status_code for r in responses] == [409] * 3
    assert all(r.json() == NOT_ACTIVE for r in responses)


async def test_foreign_member_in_a_weight_mapping_is_409(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await group_trip(client)
    _, foreign_ids = await group_trip(other_client)
    split = {"mode": "shares", "shares": {ids[0]: 1, foreign_ids[0]: 1}}

    response = await post_expense(client, trip_id, expense_body(ids[0], split))

    assert (response.status_code, response.json()) == (409, NOT_ACTIVE)


@pytest.mark.parametrize(("stated", "difference"), [(700_000, 8_000), (710_000, -2_000)])
async def test_exact_mismatch_reports_the_difference(
    client: AsyncClient, stated: int, difference: int
) -> None:
    trip_id, ids = await group_trip(client)
    split = {"mode": "exact", "amounts": {ids[0]: 500_000, ids[1]: stated - 500_000}}

    response = await post_expense(client, trip_id, expense_body(ids[0], split, amount=708_000))

    assert (response.status_code, response.json()) == (
        422,
        INVALID_SPLIT | {"difference": difference},
    )


@pytest.mark.parametrize(
    ("mode", "key", "weights"),
    [
        ("percent", "basis_points", (5000, 4999)),
        ("percent", "basis_points", (10_000, 1)),
        ("shares", "shares", (0, 0)),
    ],
)
async def test_weights_that_cannot_split_are_422(
    client: AsyncClient, mode: str, key: str, weights: tuple[int, int]
) -> None:
    trip_id, ids = await group_trip(client)
    split = {"mode": mode, key: dict(zip(ids[:2], weights, strict=True))}

    response = await post_expense(client, trip_id, expense_body(ids[0], split))

    assert (response.status_code, response.json()) == (422, INVALID_SPLIT)


async def test_locked_trip_is_403(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    await lock_trip(session, trip_id)

    response = await post_expense(
        client, trip_id, expense_body(ids[0], {"mode": "equal", "participants": ids})
    )

    assert (response.status_code, response.json()) == (403, TRIP_LOCKED)


async def test_closed_trip_is_403(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, ids = await group_trip(client)
    closed = update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(closed_at=datetime.now(UTC))
    await persist(session, closed)

    response = await post_expense(
        client, trip_id, expense_body(ids[0], {"mode": "equal", "participants": ids})
    )

    assert (response.status_code, response.json()) == (
        403,
        {"code": "trip_closed", "message": "Trip is closed"},
    )


async def test_removed_author_is_refused_by_service_after_lock(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    await remove_member(session, trip_id, 1)

    with pytest.raises(RuleViolation) as raised:
        await expenses.create_expense(
            session,
            uuid.UUID(trip_id),
            uuid.UUID(ids[1]),
            NewExpense(
                title="Lunch",
                amount=50_000,
                category="food",
                spent_on=datetime(2026, 11, 7, tzinfo=UTC).date(),
                paid_by=uuid.UUID(ids[0]),
                split_mode="equal",
                weights={uuid.UUID(ids[0]): 1},
                note=None,
                place=None,
            ),
        )

    assert raised.value.code == "member_not_active"
