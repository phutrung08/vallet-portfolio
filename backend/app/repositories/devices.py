import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Device, Member, Membership


async def find_active_device(
    session: AsyncSession, token_hash: bytes, now: datetime
) -> Device | None:
    statement = select(Device).where(
        Device.token_hash == token_hash,
        Device.revoked_at.is_(None),
        Device.expires_at > now,
    )
    return await session.scalar(statement)


def add_device(
    session: AsyncSession, token_hash: bytes, now: datetime, expires_at: datetime
) -> Device:
    device = Device(id=uuid.uuid4(), token_hash=token_hash, last_seen_at=now, expires_at=expires_at)
    session.add(device)
    return device


async def upsert_membership(
    session: AsyncSession, device_id: uuid.UUID, trip_id: uuid.UUID, member_id: uuid.UUID
) -> None:
    """Attach the device to ``member_id``, reactivating or repointing an existing row."""
    statement = insert(Membership).values(device_id=device_id, trip_id=trip_id, member_id=member_id)
    statement = statement.on_conflict_do_update(
        index_elements=[Membership.device_id, Membership.trip_id],
        set_={"member_id": statement.excluded.member_id, "revoked_at": None},
    )
    await session.execute(statement)


async def find_active_membership(
    session: AsyncSession, device_id: uuid.UUID, trip_id: uuid.UUID
) -> Membership | None:
    # No join on trips: the trip FK cascades, so a membership row implies its trip exists.
    statement = (
        select(Membership)
        .join(
            Member,
            (Member.trip_id == Membership.trip_id) & (Member.id == Membership.member_id),
        )
        .where(
            Membership.device_id == device_id,
            Membership.trip_id == trip_id,
            Membership.revoked_at.is_(None),
            Member.removed_at.is_(None),
        )
    )
    return await session.scalar(statement)


async def revoke_member_memberships(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID, now: datetime
) -> None:
    """Cut off every device that acts as ``member_id``."""
    statement = (
        update(Membership)
        .where(
            Membership.trip_id == trip_id,
            Membership.member_id == member_id,
            Membership.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await session.execute(statement)


async def revoke_membership(
    session: AsyncSession, device_id: uuid.UUID, trip_id: uuid.UUID, now: datetime
) -> bool:
    """Return whether an active membership was revoked."""
    statement = (
        update(Membership)
        .where(
            Membership.device_id == device_id,
            Membership.trip_id == trip_id,
            Membership.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    result = cast("CursorResult[object]", await session.execute(statement))
    return result.rowcount > 0


async def revoke_device(session: AsyncSession, device_id: uuid.UUID, now: datetime) -> None:
    """Stop the device's session; its memberships stay but no longer resolve."""
    await session.execute(
        update(Device)
        .where(Device.id == device_id, Device.revoked_at.is_(None))
        .values(revoked_at=now)
    )
