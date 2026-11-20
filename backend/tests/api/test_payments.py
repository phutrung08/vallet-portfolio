import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.repositories.models import Trip
from app.services import payments
from app.services.errors import RuleViolation
from app.services.payments import NewPayment
from tests.api.conftest import FrozenClock
from tests.api.test_expenses_read import MEMBERSHIP_QUERIES, recorded_statements
from tests.api.test_join_preview import persist, remove_member
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio

PAYMENT_KEYS = {"id", "payer", "payee", "amount", "paid_on", "note", "created_by", "created_at"}
NOT_ACTIVE = {"code": "member_not_active", "message": "Member is not active in this trip"}
TRIP_LOCKED = {"code": "trip_locked", "message": "Trip is locked"}


async def trip(client: AsyncClient) -> tuple[str, list[str]]:
    """Create a 3-member trip and return ``(trip_id, member_ids)``."""
    detail = await create(client)
    return detail["id"], [m["id"] for m in detail["members"]]


async def pay(
    client: AsyncClient, trip_id: str, payer: str, payee: str, amount: Any = 100_000, **extra: Any
) -> Response:
    body = {"payer": payer, "payee": payee, "amount": amount, "paid_on": "2026-11-08"} | extra
    return await client.post(f"/trips/{trip_id}/payments", json=body)


async def paid(
    client: AsyncClient, trip_id: str, payer: str, payee: str, amount: int = 100_000, **extra: Any
) -> dict[str, Any]:
    response = await pay(client, trip_id, payer, payee, amount, **extra)
    assert response.status_code == 201, response.text
    payment: dict[str, Any] = response.json()
    return payment


async def listed(client: AsyncClient, trip_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"/trips/{trip_id}/payments")
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"payments"}
    items: list[dict[str, Any]] = response.json()["payments"]
    return items


async def set_trip(session: AsyncSession, trip_id: str, **values: Any) -> None:
    await persist(session, update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(**values))


async def test_a_recorded_payment_is_returned_and_listed(
    client: AsyncClient, clock: FrozenClock
) -> None:
    trip_id, ids = await trip(client)

    payment = await paid(client, trip_id, ids[1], ids[0], 250_000, note="Bank transfer")

    assert set(payment) == PAYMENT_KEYS
    assert {k: v for k, v in payment.items() if k not in {"id", "created_at"}} == {
        "payer": ids[1],
        "payee": ids[0],
        "amount": 250_000,
        "paid_on": "2026-11-08",
        "note": "Bank transfer",
        "created_by": ids[0],
    }
    assert datetime.fromisoformat(payment["created_at"]) == clock.now
    assert await listed(client, trip_id) == [payment]


async def test_list_is_newest_first_by_day_then_time_then_id(
    client: AsyncClient, clock: FrozenClock
) -> None:
    trip_id, ids = await trip(client)
    older_day = await paid(client, trip_id, ids[1], ids[0], paid_on="2026-11-08")
    newer_day = await paid(client, trip_id, ids[1], ids[0], paid_on="2026-11-09")
    clock.advance(timedelta(minutes=1))
    later_same_day = await paid(client, trip_id, ids[2], ids[0], paid_on="2026-11-08")
    twins = [await paid(client, trip_id, ids[2], ids[1], paid_on="2026-11-07") for _ in "ab"]

    items = await listed(client, trip_id)

    twins_by_id = sorted(twins, key=lambda p: uuid.UUID(p["id"]), reverse=True)
    expected = [newer_day, later_same_day, older_day, *twins_by_id]
    assert [p["id"] for p in items] == [p["id"] for p in expected]
    assert all(set(p) == PAYMENT_KEYS for p in items)


async def test_list_shows_only_this_trips_live_payments(
    client: AsyncClient, other_client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await trip(client)
    other_id, other_ids = await trip(other_client)
    await paid(other_client, other_id, other_ids[1], other_ids[0])
    kept = await paid(client, trip_id, ids[1], ids[0])
    gone = await paid(client, trip_id, ids[2], ids[0])
    await client.delete(f"/trips/{trip_id}/payments/{gone['id']}")

    with recorded_statements(db_engine) as statements:
        items = await listed(client, trip_id)

    assert items == [kept]
    assert len(statements) == MEMBERSHIP_QUERIES + 1


async def test_a_closed_trip_still_takes_and_deletes_payments(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await trip(client)
    await set_trip(session, trip_id, closed_at=datetime.now(UTC))

    payment = await paid(client, trip_id, ids[1], ids[0])
    deleted = await client.delete(f"/trips/{trip_id}/payments/{payment['id']}")

    assert deleted.status_code == 204
    assert await listed(client, trip_id) == []


async def test_a_locked_trip_rejects_recording_and_deleting(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await trip(client)
    payment = await paid(client, trip_id, ids[1], ids[0])
    await set_trip(session, trip_id, locked_at=datetime.now(UTC))

    recorded = await pay(client, trip_id, ids[2], ids[0])
    deleted = await client.delete(f"/trips/{trip_id}/payments/{payment['id']}")

    assert (recorded.status_code, recorded.json()) == (403, TRIP_LOCKED)
    assert (deleted.status_code, deleted.json()) == (403, TRIP_LOCKED)
    assert await listed(client, trip_id) == [payment]


async def test_removed_members_may_pay_and_be_paid(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await trip(client)
    await remove_member(session, trip_id, 2)

    sent = await pay(client, trip_id, ids[2], ids[0])
    received = await pay(client, trip_id, ids[1], ids[2])

    assert [sent.status_code, received.status_code] == [201, 201]


async def test_ids_of_other_trips_and_unknown_ids_get_one_409(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await trip(client)
    _, other_ids = await trip(other_client)
    unknown = str(uuid.uuid4())

    responses = [
        await pay(client, trip_id, other_ids[1], ids[0]),
        await pay(client, trip_id, ids[0], other_ids[1]),
        await pay(client, trip_id, unknown, ids[0]),
    ]

    assert [(r.status_code, r.json()) for r in responses] == [(409, NOT_ACTIVE)] * 3
    assert await listed(client, trip_id) == []


async def test_paying_oneself_is_a_validation_error(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)

    response = await pay(client, trip_id, ids[1], ids[1])

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.parametrize("amount", [0, -1, 10**12 + 1, True, 1.5, "100000", None])
async def test_amounts_out_of_range_or_not_integers_are_422(
    client: AsyncClient, amount: Any
) -> None:
    trip_id, ids = await trip(client)

    response = await pay(client, trip_id, ids[1], ids[0], amount)

    assert response.status_code == 422
    assert response.json()["fields"] == ["body.amount"]


async def test_the_largest_amount_is_accepted(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)

    assert (await pay(client, trip_id, ids[1], ids[0], 10**12)).status_code == 201


async def test_notes_are_normalised(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)
    decomposed = unicodedata.normalize("NFD", "  Cafe sett\u00e9d  ")

    note = await paid(client, trip_id, ids[1], ids[0], note=decomposed)
    blank = await paid(client, trip_id, ids[1], ids[0], note="   ")

    assert note["note"] == "Cafe sett\u00e9d"
    assert blank["note"] is None


@pytest.mark.parametrize(
    "extra",
    [{"note": "x" * 201}, {"note": "a\nb"}, {"note": "a\u202eb"}, {"paid_on": "08/11/2026"}],
)
async def test_bad_notes_and_dates_are_422(client: AsyncClient, extra: dict[str, Any]) -> None:
    trip_id, ids = await trip(client)

    response = await pay(client, trip_id, ids[1], ids[0], **extra)

    assert response.status_code == 422


async def test_unknown_fields_and_missing_fields_are_422(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)
    url = f"/trips/{trip_id}/payments"
    full = {"payer": ids[1], "payee": ids[0], "amount": 1_000, "paid_on": "2026-11-08"}

    extra = await client.post(url, json=full | {"created_by": ids[2]})
    missing = await client.post(url, json={k: v for k, v in full.items() if k != "paid_on"})

    assert [extra.status_code, missing.status_code] == [422, 422]


async def test_unknown_deleted_and_foreign_payments_are_the_same_404(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, ids = await trip(client)
    other_id, other_ids = await trip(other_client)
    foreign = await paid(other_client, other_id, other_ids[1], other_ids[0])
    gone = await paid(client, trip_id, ids[1], ids[0])
    assert (await client.delete(f"/trips/{trip_id}/payments/{gone['id']}")).status_code == 204

    responses = [
        await client.delete(f"/trips/{trip_id}/payments/{payment_id}")
        for payment_id in (uuid.uuid4(), gone["id"], foreign["id"])
    ]

    assert [(r.status_code, r.json()) for r in responses] == [(404, NOT_FOUND)] * 3
    assert len(await listed(other_client, other_id)) == 1


async def test_removed_caller_is_refused_by_payment_services_after_lock(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    trip_id, ids = await trip(client)
    payment = await paid(client, trip_id, ids[1], ids[0])
    await remove_member(session, trip_id, 2)

    with pytest.raises(RuleViolation) as rec_err:
        await payments.record_payment(
            session,
            uuid.UUID(trip_id),
            uuid.UUID(ids[2]),
            NewPayment(uuid.UUID(ids[1]), uuid.UUID(ids[0]), 1_000, clock.now.date(), None),
            clock.now,
        )
    with pytest.raises(RuleViolation) as del_err:
        await payments.delete_payment(
            session, uuid.UUID(trip_id), uuid.UUID(payment["id"]), uuid.UUID(ids[2]), clock.now
        )

    assert rec_err.value.code == "member_not_active"
    assert del_err.value.code == "member_not_active"
