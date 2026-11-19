import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import expenses as expense_repository
from app.repositories import trips as trip_repository
from app.services.errors import RuleViolation
from app.services.trip_guards import lock_trip_for_actor
from tests.db.factories import (
    add_trip,
    make_device,
    make_expense,
    make_membership,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)


async def test_lock_trip_for_actor_handles_missing_removed_locked_and_closed(
    session: AsyncSession,
) -> None:
    trip, (an, binh) = await add_trip(session)

    assert await lock_trip_for_actor(session, uuid.uuid4(), an.id) is None

    locked = await lock_trip_for_actor(session, trip.id, an.id)
    assert locked is not None and locked.id == trip.id

    shared = await lock_trip_for_actor(session, trip.id, binh.id, exclusive=False)
    assert shared is not None and shared.id == trip.id

    binh.removed_at = NOW
    await session.flush()
    with pytest.raises(RuleViolation) as removed_err:
        await lock_trip_for_actor(session, trip.id, binh.id)
    assert removed_err.value.code == "member_not_active"

    trip.locked_at = NOW
    await session.flush()
    with pytest.raises(RuleViolation) as locked_err:
        await lock_trip_for_actor(session, trip.id, an.id)
    assert locked_err.value.code == "trip_locked"
    assert await lock_trip_for_actor(session, trip.id, an.id, require_open=False) is not None

    trip.closed_at = NOW
    trip.locked_at = None
    await session.flush()
    with pytest.raises(RuleViolation) as closed_err:
        await lock_trip_for_actor(session, trip.id, an.id)
    assert closed_err.value.code == "trip_closed"
    assert await lock_trip_for_actor(session, trip.id, an.id, require_open=False) is not None

    trip.locked_at = NOW
    await session.flush()
    with pytest.raises(RuleViolation) as locked_over_closed:
        await lock_trip_for_actor(session, trip.id, an.id)
    assert locked_over_closed.value.code == "trip_locked"


async def test_joined_checks_exclude_revoked_and_expired_devices(session: AsyncSession) -> None:
    trip, members = await add_trip(session, member_count=4)
    active_m, revoked_dev_m, expired_dev_m, revoked_mem_m = members

    live_device = make_device(expires_at=NOW + timedelta(days=1))
    revoked_device = make_device(expires_at=NOW + timedelta(days=1), revoked_at=NOW)
    expired_device = make_device(expires_at=NOW - timedelta(minutes=1))
    live_device_2 = make_device(expires_at=NOW + timedelta(days=1))
    session.add_all([live_device, revoked_device, expired_device, live_device_2])
    await session.flush()

    session.add_all(
        [
            make_membership(live_device, active_m),
            make_membership(revoked_device, revoked_dev_m),
            make_membership(expired_device, expired_dev_m),
            make_membership(live_device_2, revoked_mem_m, revoked_at=NOW),
        ]
    )
    await session.flush()

    rows = await trip_repository.list_active_members_with_joined(session, trip.id, NOW)
    assert [(m.id, joined) for m, joined in rows] == [
        (active_m.id, True),
        (revoked_dev_m.id, False),
        (expired_dev_m.id, False),
        (revoked_mem_m.id, False),
    ]

    assert await trip_repository.is_member_joined(session, trip.id, active_m.id, NOW) is True
    assert (
        await trip_repository.is_member_joined(
            session, trip.id, active_m.id, NOW, exclude_device_id=live_device.id
        )
        is False
    )
    assert await trip_repository.is_member_joined(session, trip.id, revoked_dev_m.id, NOW) is False
    assert await trip_repository.is_member_joined(session, trip.id, expired_dev_m.id, NOW) is False
    assert await trip_repository.is_member_joined(session, trip.id, revoked_mem_m.id, NOW) is False


async def test_device_trip_and_total_member_counts(session: AsyncSession) -> None:
    trip, (an, binh) = await add_trip(session, member_count=2)
    other_trip, (chi, _) = await add_trip(session, member_count=2)
    device = make_device(expires_at=NOW + timedelta(days=1))
    session.add(device)
    await session.flush()
    session.add_all([make_membership(device, an), make_membership(device, chi)])
    await session.flush()

    assert await trip_repository.count_device_trips(session, device.id) == 2

    binh.removed_at = NOW
    chi.removed_at = NOW
    await session.flush()

    assert await trip_repository.count_device_trips(session, device.id) == 1
    assert await trip_repository.count_total_members(session, trip.id) == 2
    assert await trip_repository.count_total_members(session, other_trip.id) == 2


async def test_expense_category_and_payer_totals_group_live_rows(session: AsyncSession) -> None:
    trip, (an, binh) = await add_trip(session)
    trip.fund_holder_id = an.id
    e1 = make_expense(trip, an, an, category="food", amount=100_000)
    e2 = make_expense(trip, an, an, category="food", amount=250_000)
    e3 = make_expense(trip, None, an, category="lodging", amount=500_000)
    deleted = make_expense(trip, binh, binh, category="transport", amount=900_000, deleted_at=NOW)
    session.add_all([e1, e2, e3, deleted])
    await session.flush()

    assert list(await expense_repository.category_totals(session, trip.id)) == [
        ("lodging", 1, 500_000),
        ("food", 2, 350_000),
    ]
    assert list(await expense_repository.payer_totals(session, trip.id)) == [
        (None, 1, 500_000),
        (an.id, 2, 350_000),
    ]
