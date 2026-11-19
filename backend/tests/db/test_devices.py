from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Device, Membership, Trip
from tests.db.factories import add_trip, assert_rejected, make_device, make_membership

pytestmark = pytest.mark.anyio


def new_device(session: AsyncSession) -> Device:
    device = make_device()
    session.add(device)
    return device


async def test_token_hash_must_be_32_bytes(session: AsyncSession) -> None:
    short = Device(token_hash=b"\x00" * 31, expires_at=datetime.now(UTC))

    await assert_rejected(session, "ck_devices_token_hash_length", short)


async def test_membership_for_member_of_another_trip_is_rejected(session: AsyncSession) -> None:
    trip, _ = await add_trip(session)
    _, (outsider, _) = await add_trip(session)
    device = new_device(session)
    await session.flush()

    membership = make_membership(device, outsider, trip_id=trip.id)
    await assert_rejected(session, "fk_memberships_trip_id_member_id_members", membership)


async def test_device_has_one_membership_per_trip(session: AsyncSession) -> None:
    trip, (an, binh) = await add_trip(session)
    device = new_device(session)
    await session.flush()
    session.add(make_membership(device, an))
    await session.flush()

    await assert_rejected(session, "pk_memberships", make_membership(device, binh))


async def test_deleting_a_device_or_trip_removes_its_memberships(session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    other, (chi, _) = await add_trip(session)
    device = new_device(session)
    second = new_device(session)
    await session.flush()
    session.add_all([make_membership(device, an), make_membership(second, chi)])
    await session.flush()

    await session.execute(delete(Device).where(Device.id == device.id))
    await session.execute(delete(Trip).where(Trip.id == other.id))

    remaining = select(func.count()).where(Membership.trip_id.in_([trip.id, other.id]))
    assert await session.scalar(remaining) == 0
