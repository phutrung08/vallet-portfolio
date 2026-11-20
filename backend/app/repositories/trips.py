import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Device, Member, Membership, Trip


async def add_trip(
    session: AsyncSession, trip: Trip, members: Sequence[Member], membership: Membership
) -> None:
    session.add(trip)
    # The trip <-> member FK cycle (fund holder) leaves the unit of work unable to order
    # these inserts, so the trip goes first.
    await session.flush()
    session.add_all(members)
    session.add(membership)


async def find_trip(session: AsyncSession, trip_id: uuid.UUID) -> Trip | None:
    return await session.get(Trip, trip_id)


async def list_members(session: AsyncSession, trip_id: uuid.UUID) -> Sequence[Member]:
    statement = select(Member).where(Member.trip_id == trip_id).order_by(Member.position)
    return (await session.scalars(statement)).all()


async def count_total_members(session: AsyncSession, trip_id: uuid.UUID) -> int:
    """Count all member rows (including soft-removed ones) for hard ceiling checks."""
    statement = select(func.count()).select_from(Member).where(Member.trip_id == trip_id)
    return int(await session.scalar(statement) or 0)


async def find_trip_with_members(
    session: AsyncSession, trip_id: uuid.UUID
) -> tuple[Trip, Sequence[Member]] | None:
    """Return the trip and all its members (removed ones too) by position in one query."""
    statement = (
        select(Trip, Member)
        .join(Member, Member.trip_id == Trip.id)
        .where(Trip.id == trip_id)
        .order_by(Member.position)
        .execution_options(populate_existing=True)
    )
    rows = (await session.execute(statement)).all()
    return (rows[0][0], [member for _, member in rows]) if rows else None


def add_member(session: AsyncSession, member: Member) -> None:
    session.add(member)


async def find_trip_by_share_token_hash(session: AsyncSession, token_hash: bytes) -> Trip | None:
    return await session.scalar(select(Trip).where(Trip.share_token_hash == token_hash))


def _locked(statement: Select[Trip]) -> Select[Trip]:
    """Lock the selected trip row until commit, so writes to one trip run one after another.

    FOR NO KEY UPDATE rather than FOR UPDATE: it still conflicts with other joins and with any
    UPDATE of the trip (lock, rotate), but not with the FOR KEY SHARE that inserts of expenses
    and members take for their trip FK, so a lock never stalls unrelated writes.
    """
    return statement.with_for_update(key_share=True).execution_options(populate_existing=True)


async def lock_trip_by_share_token_hash(session: AsyncSession, token_hash: bytes) -> Trip | None:
    return await session.scalar(_locked(select(Trip).where(Trip.share_token_hash == token_hash)))


async def lock_trip(session: AsyncSession, trip_id: uuid.UUID) -> Trip | None:
    return await session.scalar(_locked(select(Trip).where(Trip.id == trip_id)))


async def share_lock_trip(session: AsyncSession, trip_id: uuid.UUID) -> Trip | None:
    # FOR SHARE waits for, and then blocks, member changes and trip updates (FOR NO KEY UPDATE)
    # until commit, but not other FOR SHARE holders, so expense writes never queue on each other.
    statement = select(Trip).where(Trip.id == trip_id).with_for_update(read=True)
    return await session.scalar(statement.execution_options(populate_existing=True))


async def find_member(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> Member | None:
    """Return a single member row (including removed members), or None when absent."""
    statement = select(Member).where(Member.trip_id == trip_id, Member.id == member_id)
    return await session.scalar(statement)


async def find_active_member(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> Member | None:
    statement = select(Member).where(
        Member.trip_id == trip_id, Member.id == member_id, Member.removed_at.is_(None)
    )
    return await session.scalar(statement)


def _active_device_membership(now: datetime) -> Select[uuid.UUID]:
    return (
        select(Membership.device_id)
        .join(Device, Device.id == Membership.device_id)
        .where(
            Membership.trip_id == Member.trip_id,
            Membership.member_id == Member.id,
            Membership.revoked_at.is_(None),
            Device.revoked_at.is_(None),
            Device.expires_at > now,
        )
    )


async def list_active_members_with_joined(
    session: AsyncSession, trip_id: uuid.UUID, now: datetime
) -> Sequence[tuple[Member, bool]]:
    """Return active members by position, each paired with live non-expired device status."""
    joined = _active_device_membership(now).correlate(Member).exists()
    statement = (
        select(Member, joined)
        .where(Member.trip_id == trip_id, Member.removed_at.is_(None))
        .order_by(Member.position)
    )
    result = await session.execute(statement)
    return [(member, bool(is_joined)) for member, is_joined in result]


async def is_member_joined(
    session: AsyncSession,
    trip_id: uuid.UUID,
    member_id: uuid.UUID,
    now: datetime,
    *,
    exclude_device_id: uuid.UUID | None = None,
) -> bool:
    """Return whether an active device currently claims ``member_id`` in ``trip_id``."""
    statement = (
        select(Membership.device_id)
        .join(Device, Device.id == Membership.device_id)
        .where(
            Membership.trip_id == trip_id,
            Membership.member_id == member_id,
            Membership.revoked_at.is_(None),
            Device.revoked_at.is_(None),
            Device.expires_at > now,
        )
    )
    if exclude_device_id is not None:
        statement = statement.where(Membership.device_id != exclude_device_id)
    return bool(await session.scalar(select(exists(statement))))


async def count_device_trips(session: AsyncSession, device_id: uuid.UUID) -> int:
    """Count active trips this device belongs to."""
    statement = (
        select(func.count())
        .select_from(Membership)
        .join(Member, (Member.trip_id == Membership.trip_id) & (Member.id == Membership.member_id))
        .where(
            Membership.device_id == device_id,
            Membership.revoked_at.is_(None),
            Member.removed_at.is_(None),
        )
    )
    return int(await session.scalar(statement) or 0)


async def list_device_trips(
    session: AsyncSession, device_id: uuid.UUID
) -> Sequence[tuple[Trip, uuid.UUID, int]]:
    """Return trips the device is an active member of, with member id and active head count."""
    active_members = (
        select(func.count())
        .select_from(Member)
        .where(Member.trip_id == Trip.id, Member.removed_at.is_(None))
        .correlate(Trip)
        .scalar_subquery()
    )
    statement = (
        select(Trip, Membership.member_id, active_members)
        .join(Membership, Membership.trip_id == Trip.id)
        .join(Member, (Member.trip_id == Membership.trip_id) & (Member.id == Membership.member_id))
        .where(
            Membership.device_id == device_id,
            Membership.revoked_at.is_(None),
            Member.removed_at.is_(None),
        )
        .order_by(
            Trip.closed_at.is_not(None), Trip.starts_on.desc().nulls_last(), Trip.created_at.desc()
        )
    )
    result = await session.execute(statement)
    return [(trip, member_id, count) for trip, member_id, count in result]
