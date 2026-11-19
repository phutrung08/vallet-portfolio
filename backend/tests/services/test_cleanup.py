import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Device, IdempotencyKey, Member, Membership
from app.services.cleanup import (
    DEVICE_GRACE,
    IDEMPOTENCY_TTL,
    CleanupCounts,
    delete_expired_data,
)
from tests.db.factories import add_trip, make_membership

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
DAY = timedelta(days=1)


def add_device(
    session: AsyncSession, expires_at: datetime, revoked_at: datetime | None = None
) -> Device:
    token_hash = hashlib.sha256(secrets.token_bytes(8)).digest()
    device = Device(
        id=uuid.uuid4(), token_hash=token_hash, expires_at=expires_at, revoked_at=revoked_at
    )
    session.add(device)
    return device


def add_key(session: AsyncSession, device: Device, created_at: datetime) -> IdempotencyKey:
    row = IdempotencyKey(
        device_id=device.id,
        key=uuid.uuid4(),
        route="POST /trips",
        request_hash=b"\x00" * 32,
        created_at=created_at,
    )
    session.add(row)
    return row


async def count(session: AsyncSession, model: type[Device | IdempotencyKey | Membership]) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def surviving_ids(session: AsyncSession, *devices: Device) -> set[uuid.UUID]:
    ids = [device.id for device in devices]
    return set(await session.scalars(select(Device.id).where(Device.id.in_(ids))))


async def test_only_devices_past_the_grace_period_are_deleted(session: AsyncSession) -> None:
    long_expired = add_device(session, NOW - DEVICE_GRACE - DAY)
    long_revoked = add_device(session, NOW + 90 * DAY, revoked_at=NOW - DEVICE_GRACE - DAY)
    just_expired = add_device(session, NOW - DEVICE_GRACE + DAY)
    just_revoked = add_device(session, NOW + 90 * DAY, revoked_at=NOW - DAY)
    live = add_device(session, NOW + 90 * DAY)
    await session.flush()

    counts = await delete_expired_data(session, NOW)

    assert counts == CleanupCounts(devices=2, idempotency_keys=0)
    assert await surviving_ids(
        session, long_expired, long_revoked, just_expired, just_revoked, live
    ) == {just_expired.id, just_revoked.id, live.id}


async def test_dead_devices_lose_memberships_but_trip_data_stays(session: AsyncSession) -> None:
    trip, (an, binh) = await add_trip(session)
    dead = add_device(session, NOW - DEVICE_GRACE - DAY)
    live = add_device(session, NOW + 90 * DAY)
    await session.flush()
    session.add_all([make_membership(dead, an), make_membership(live, binh)])
    add_key(session, dead, NOW)
    await session.flush()

    await delete_expired_data(session, NOW)

    kept = set(
        await session.scalars(select(Membership.member_id).where(Membership.trip_id == trip.id))
    )
    assert kept == {binh.id}
    members = await session.scalars(select(Member.id).where(Member.trip_id == trip.id))
    assert set(members) == {an.id, binh.id}
    assert (
        await session.scalar(select(IdempotencyKey.key).where(IdempotencyKey.device_id == dead.id))
        is None
    )


async def test_idempotency_keys_older_than_a_day_are_deleted(session: AsyncSession) -> None:
    live = add_device(session, NOW + 90 * DAY)
    old = add_key(session, live, NOW - IDEMPOTENCY_TTL - timedelta(minutes=1))
    fresh = add_key(session, live, NOW - IDEMPOTENCY_TTL + timedelta(minutes=1))
    await session.flush()

    await delete_expired_data(session, NOW)

    left = set(
        await session.scalars(select(IdempotencyKey.key).where(IdempotencyKey.device_id == live.id))
    )
    assert left == {fresh.key}
    assert old.key not in left


async def test_batches_cover_more_rows_than_one_batch(session: AsyncSession) -> None:
    dead = [add_device(session, NOW - DEVICE_GRACE - DAY) for _ in range(7)]
    live = add_device(session, NOW + 90 * DAY)
    for _ in range(5):
        add_key(session, live, NOW - 2 * DAY)
    await session.flush()

    counts = await delete_expired_data(session, NOW, batch_size=3)

    assert counts == CleanupCounts(devices=7, idempotency_keys=5)
    assert await surviving_ids(session, *dead) == set()
    assert await surviving_ids(session, live) == {live.id}
    assert await count(session, IdempotencyKey) == 0
