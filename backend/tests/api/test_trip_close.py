import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Member, Trip
from app.services import trips
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_trip_lock import TRIP_LOCKED
from tests.api.test_trips import DETAIL_KEYS, NOT_FOUND, create

pytestmark = pytest.mark.anyio


async def closed_at(session: AsyncSession, trip_id: str) -> datetime | None:
    statement = (
        select(Trip.closed_at)
        .where(Trip.id == uuid.UUID(trip_id))
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def test_close_marks_the_trip_closed_with_the_clock_time(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)

    response = await client.post(f"/trips/{detail['id']}/close")

    assert response.status_code == 200
    assert set(response.json()) == DETAIL_KEYS
    assert response.json() == detail | {"closed": True}
    assert await closed_at(session, detail["id"]) == clock.now
    assert (await client.get(f"/trips/{detail['id']}")).json()["closed"] is True


async def test_closing_twice_keeps_the_first_closing_time(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)
    first = await client.post(f"/trips/{detail['id']}/close")
    first_time = clock.now
    clock.advance(timedelta(hours=1))

    second = await client.post(f"/trips/{detail['id']}/close")

    assert (second.status_code, second.json()) == (200, first.json())
    assert await closed_at(session, detail["id"]) == first_time


async def test_reopen_clears_the_closing_and_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/close")

    reopened = await client.post(f"/trips/{detail['id']}/reopen")
    again = await client.post(f"/trips/{detail['id']}/reopen")

    assert (reopened.status_code, reopened.json()) == (200, detail)
    assert (again.status_code, again.json()) == (200, detail)
    assert await closed_at(session, detail["id"]) is None


async def test_the_trip_list_puts_closed_trips_last(client: AsyncClient) -> None:
    closing = await create(client, name="closing", starts_on="2027-01-01")
    open_trip = await create(client, name="open", starts_on="2026-01-01")
    await client.post(f"/trips/{closing['id']}/close")

    listed_trips = (await client.get("/trips")).json()["trips"]

    assert [(t["id"], t["closed"]) for t in listed_trips] == [
        (open_trip["id"], False),
        (closing["id"], True),
    ]


async def test_a_locked_trip_can_be_neither_closed_nor_reopened(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/close")
    await session.execute(
        update(Trip).where(Trip.id == uuid.UUID(detail["id"])).values(locked_at=datetime.now(UTC))
    )
    await session.commit()

    reopen = await client.post(f"/trips/{detail['id']}/reopen")
    other = await create(client, name="other")
    await session.execute(
        update(Trip).where(Trip.id == uuid.UUID(other["id"])).values(locked_at=datetime.now(UTC))
    )
    await session.commit()
    close = await client.post(f"/trips/{other['id']}/close")

    assert (reopen.status_code, reopen.json()) == (403, TRIP_LOCKED)
    assert (close.status_code, close.json()) == (403, TRIP_LOCKED)
    assert await closed_at(session, detail["id"]) is not None
    assert await closed_at(session, other["id"]) is None


async def test_a_member_removed_before_the_lock_cannot_close_or_reopen(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)
    trip_id, caller = uuid.UUID(detail["id"]), uuid.UUID(detail["me"])
    await session.execute(update(Member).where(Member.id == caller).values(removed_at=clock.now))
    await session.commit()

    with pytest.raises(RuleViolation) as closing:
        await trips.close_trip(session, trip_id, caller, clock.now)
    with pytest.raises(RuleViolation) as reopening:
        await trips.reopen_trip(session, trip_id, caller, clock.now)

    assert (closing.value.code, reopening.value.code) == ("member_not_active",) * 2
    assert (await client.post(f"/trips/{trip_id}/close")).status_code == 404


async def test_outsiders_get_404(client: AsyncClient, other_client: AsyncClient) -> None:
    detail = await create(client)

    responses = [
        await other_client.post(f"/trips/{detail['id']}/{action}") for action in ("close", "reopen")
    ]

    assert [(r.status_code, r.json()) for r in responses] == [(404, NOT_FOUND)] * 2


async def test_closed_trip_rejects_expense_member_fund_writes_but_allows_settlement_writes(
    client: AsyncClient,
) -> None:
    trip_closed = {"code": "trip_closed", "message": "Trip is closed"}
    detail = await create(client, uses_fund=True, creator_name="An", member_names=["Binh", "Chi"])
    trip_id = detail["id"]
    ids = [m["id"] for m in detail["members"]]
    expense_resp = await client.post(
        f"/trips/{trip_id}/expenses",
        json={
            "title": "Dinner",
            "amount": 100_000,
            "category": "food",
            "spent_on": "2026-11-07",
            "paid_by": ids[0],
            "split": {"mode": "equal", "participants": ids},
        },
    )
    contrib_resp = await client.post(
        f"/trips/{trip_id}/fund/contributions",
        json={"member_id": ids[0], "amount": 50_000, "contributed_on": "2026-11-07"},
    )
    await client.post(f"/trips/{trip_id}/close")

    refused = [
        await client.post(f"/trips/{trip_id}/members", json={"display_name": "Dung"}),
        await client.patch(f"/trips/{trip_id}/members/{ids[1]}", json={"display_name": "Ben"}),
        await client.delete(f"/trips/{trip_id}/members/{ids[1]}"),
        await client.post(
            f"/trips/{trip_id}/expenses",
            json={
                "title": "Coffee",
                "amount": 30_000,
                "category": "food",
                "spent_on": "2026-11-07",
                "paid_by": ids[0],
                "split": {"mode": "equal", "participants": ids},
            },
        ),
        await client.put(
            f"/trips/{trip_id}/expenses/{expense_resp.json()['id']}",
            json={
                "title": "Dinner",
                "amount": 120_000,
                "category": "food",
                "spent_on": "2026-11-07",
                "paid_by": ids[0],
                "split": {"mode": "equal", "participants": ids},
                "version": 1,
            },
        ),
        await client.delete(f"/trips/{trip_id}/expenses/{expense_resp.json()['id']}"),
        await client.put(f"/trips/{trip_id}/fund", json={"holder_id": ids[1]}),
        await client.post(
            f"/trips/{trip_id}/fund/contributions",
            json={"member_id": ids[0], "amount": 10_000, "contributed_on": "2026-11-07"},
        ),
        await client.delete(f"/trips/{trip_id}/fund/contributions/{contrib_resp.json()['id']}"),
    ]
    assert [(r.status_code, r.json()) for r in refused] == [(403, trip_closed)] * len(refused)

    # Settlement writes remain open while the trip is closed and unlocked.
    pay = await client.post(
        f"/trips/{trip_id}/payments",
        json={"payer": ids[1], "payee": ids[0], "amount": 25_000, "paid_on": "2026-11-08"},
    )
    del_pay = await client.delete(f"/trips/{trip_id}/payments/{pay.json()['id']}")
    put_bank = await client.put(
        f"/trips/{trip_id}/members/me/bank-account",
        json={"bank_bin": "970436", "account_number": "0123456789", "account_name": "An"},
    )
    del_bank = await client.delete(f"/trips/{trip_id}/members/me/bank-account")

    assert (pay.status_code, del_pay.status_code, put_bank.status_code, del_bank.status_code) == (
        201,
        204,
        200,
        204,
    )
