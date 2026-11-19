import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.core.security import derive_share_token, hash_token
from app.repositories import events
from app.repositories import trips as repository
from app.repositories.models import Member, Membership, Trip
from app.services.errors import RuleViolation
from app.services.trip_guards import lock_trip_for_actor, require_unlocked_trip

FIRST_SHARE_TOKEN_VERSION = 1


@dataclass(frozen=True)
class NewTrip:
    """Normalized creation inputs for a new trip."""

    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    uses_fund: bool
    creator_name: str
    member_names: Sequence[str]


@dataclass(frozen=True)
class MemberView:
    """Serialized view of a trip member."""

    id: uuid.UUID
    display_name: str
    position: int
    removed: bool


@dataclass(frozen=True)
class TripDetail:
    """Full trip state visible to an active member."""

    id: uuid.UUID
    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    fund_holder_id: uuid.UUID | None
    locked: bool
    closed: bool
    me: uuid.UUID
    members: Sequence[MemberView]


@dataclass(frozen=True)
class TripSummary:
    """Compact trip list entry for the caller's home screen."""

    id: uuid.UUID
    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    uses_fund: bool
    closed: bool
    member_count: int
    me: uuid.UUID


@dataclass(frozen=True)
class ShareLink:
    """Active share token and version for inviting members."""

    token: str
    version: int


def member_view(member: Member) -> MemberView:
    """Convert a ``Member`` ORM row into a ``MemberView`` DTO."""
    return MemberView(
        member.id, member.display_name, member.position, member.removed_at is not None
    )


def _detail(trip: Trip, members: Sequence[Member], me: uuid.UUID) -> TripDetail:
    return TripDetail(
        id=trip.id,
        name=trip.name,
        currency=trip.currency,
        starts_on=trip.starts_on,
        ends_on=trip.ends_on,
        fund_holder_id=trip.fund_holder_id,
        locked=trip.locked_at is not None,
        closed=trip.closed_at is not None,
        me=me,
        members=[member_view(m) for m in members],
    )


async def create_trip(
    session: AsyncSession, device_id: uuid.UUID, share_link_key: bytes, data: NewTrip
) -> TripDetail:
    """Create a trip whose position-0 creator member is attached to ``device_id``."""
    if await repository.count_device_trips(session, device_id) >= limits.MAX_TRIPS_PER_DEVICE:
        raise RuleViolation("device_trip_limit_reached")
    names = [data.creator_name, *data.member_names]
    if len(names) > limits.MAX_ACTIVE_MEMBERS:
        raise RuleViolation("trip_full")
    trip_id = uuid.uuid4()
    members = [
        Member(id=uuid.uuid4(), trip_id=trip_id, display_name=name, position=position)
        for position, name in enumerate(names)
    ]
    creator = members[0]
    token = derive_share_token(share_link_key, trip_id, FIRST_SHARE_TOKEN_VERSION)
    trip = Trip(
        id=trip_id,
        name=data.name,
        currency=data.currency,
        starts_on=data.starts_on,
        ends_on=data.ends_on,
        fund_holder_id=creator.id if data.uses_fund else None,
        share_token_hash=hash_token(token),
        share_token_version=FIRST_SHARE_TOKEN_VERSION,
        locked_at=None,
        closed_at=None,
    )
    membership = Membership(device_id=device_id, trip_id=trip_id, member_id=creator.id)
    await repository.add_trip(session, trip, members, membership)
    return _detail(trip, members, creator.id)


async def get_trip_detail(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> TripDetail | None:
    """Load the trip and its members in one joined query."""
    found = await repository.find_trip_with_members(session, trip_id)
    if found is None:
        return None
    trip, members = found
    return _detail(trip, members, member_id)


async def list_trips(session: AsyncSession, device_id: uuid.UUID | None) -> list[TripSummary]:
    """Return every active trip belonging to ``device_id``, ordered open-first."""
    if device_id is None:
        return []
    rows = await repository.list_device_trips(session, device_id)
    return [
        TripSummary(
            id=trip.id,
            name=trip.name,
            currency=trip.currency,
            starts_on=trip.starts_on,
            ends_on=trip.ends_on,
            uses_fund=trip.fund_holder_id is not None,
            closed=trip.closed_at is not None,
            member_count=member_count,
            me=member_id,
        )
        for trip, member_id, member_count in rows
    ]


async def get_share_link(
    session: AsyncSession, share_link_key: bytes, trip_id: uuid.UUID
) -> ShareLink | None:
    """Return the active share link derived from the trip's current version."""
    trip = await repository.find_trip(session, trip_id)
    if trip is None:
        return None
    version = trip.share_token_version
    return ShareLink(derive_share_token(share_link_key, trip_id, version), version)


async def rotate_share_link(
    session: AsyncSession,
    share_link_key: bytes,
    trip_id: uuid.UUID,
    member_id: uuid.UUID,
    now: datetime,
) -> ShareLink | None:
    """Issue a new share link, invalidating the old token for future joins."""
    trip = await lock_trip_for_actor(session, trip_id, member_id, require_open=False)
    if trip is None:
        return None
    require_unlocked_trip(trip)
    version = trip.share_token_version + 1
    token = derive_share_token(share_link_key, trip_id, version)
    trip.share_token_version = version
    trip.share_token_hash = hash_token(token)
    events.add_event(session, trip_id, "share_link_rotated", member_id, None, now)
    return ShareLink(token, version)


async def close_trip(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID, now: datetime
) -> TripDetail | None:
    """Close the trip (stopping expenses/fund edits while keeping settlement payments open)."""
    trip = await lock_trip_for_actor(session, trip_id, member_id, require_open=False)
    if trip is None:
        return None
    require_unlocked_trip(trip)
    if trip.closed_at is None:
        trip.closed_at = now
        events.add_event(session, trip_id, "trip_closed", member_id, None, now)
    return _detail(trip, await repository.list_members(session, trip_id), member_id)


async def reopen_trip(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID, now: datetime
) -> TripDetail | None:
    """Reopen a closed trip if it is not locked."""
    trip = await lock_trip_for_actor(session, trip_id, member_id, require_open=False)
    if trip is None:
        return None
    require_unlocked_trip(trip)
    if trip.closed_at is not None:
        trip.closed_at = None
        events.add_event(session, trip_id, "trip_reopened", member_id, None, now)
    return _detail(trip, await repository.list_members(session, trip_id), member_id)


async def lock_trip(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID, now: datetime
) -> TripDetail | None:
    """Make the trip read-only for everyone; locking twice keeps the first timestamp."""
    trip = await lock_trip_for_actor(session, trip_id, member_id, require_open=False)
    if trip is None:
        return None
    if trip.locked_at is None:
        trip.locked_at = now
        events.add_event(session, trip_id, "trip_locked", member_id, None, now)
    return _detail(trip, await repository.list_members(session, trip_id), member_id)


async def unlock_trip(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID, now: datetime
) -> TripDetail | None:
    """Unlock a locked trip."""
    trip = await lock_trip_for_actor(session, trip_id, member_id, require_open=False)
    if trip is None:
        return None
    if trip.locked_at is not None:
        trip.locked_at = None
        events.add_event(session, trip_id, "trip_unlocked", member_id, None, now)
    return _detail(trip, await repository.list_members(session, trip_id), member_id)
