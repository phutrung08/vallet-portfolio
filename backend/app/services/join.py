"""Joining a trip through its share link with active-slot protection."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.core.security import hash_token, is_well_formed_token
from app.repositories import devices as device_repository
from app.repositories import events
from app.repositories import trips as repository
from app.services import members, trips
from app.services.errors import RuleViolation
from app.services.trip_guards import require_unlocked_trip
from app.services.trips import TripDetail


@dataclass(frozen=True)
class PreviewTrip:
    """Public trip metadata visible from a valid share link."""

    id: uuid.UUID
    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    locked: bool
    closed: bool


@dataclass(frozen=True)
class PreviewMember:
    """Active trip member shown during share-link selection."""

    id: uuid.UUID
    display_name: str
    joined: bool


@dataclass(frozen=True)
class JoinPreview:
    """Preview payload returned for ``POST /join/preview``."""

    trip: PreviewTrip
    members: Sequence[PreviewMember]
    me: uuid.UUID | None


def _share_token_hash(token: str) -> bytes | None:
    # Malformed, unknown, and rotated-away tokens all end as 404 so probes reveal nothing.
    return hash_token(token) if is_well_formed_token(token) else None


async def preview_trip(
    session: AsyncSession, token: str, device_id: uuid.UUID | None, now: datetime
) -> JoinPreview | None:
    """Return active trip members with accurate live device claim flags."""
    token_hash = _share_token_hash(token)
    trip = (
        None
        if token_hash is None
        else await repository.find_trip_by_share_token_hash(session, token_hash)
    )
    if trip is None:
        return None
    rows = await repository.list_active_members_with_joined(session, trip.id, now)
    return JoinPreview(
        trip=PreviewTrip(
            id=trip.id,
            name=trip.name,
            currency=trip.currency,
            starts_on=trip.starts_on,
            ends_on=trip.ends_on,
            locked=trip.locked_at is not None,
            closed=trip.closed_at is not None,
        ),
        members=[PreviewMember(m.id, m.display_name, joined) for m, joined in rows],
        me=await _current_member(session, device_id, trip.id),
    )


async def _current_member(
    session: AsyncSession, device_id: uuid.UUID | None, trip_id: uuid.UUID
) -> uuid.UUID | None:
    if device_id is None:
        return None
    membership = await device_repository.find_active_membership(session, device_id, trip_id)
    return None if membership is None else membership.member_id


async def join_trip(
    session: AsyncSession,
    device_id: uuid.UUID,
    token: str,
    choice: uuid.UUID | str,
    now: datetime,
) -> TripDetail | None:
    """Attach ``device_id`` to an unjoined member or create a new member in the trip."""
    token_hash = _share_token_hash(token)
    trip = (
        None
        if token_hash is None
        else await repository.lock_trip_by_share_token_hash(session, token_hash)
    )
    if trip is None:
        return None
    require_unlocked_trip(trip)
    current = await device_repository.find_active_membership(session, device_id, trip.id)
    if (
        current is None
        and await repository.count_device_trips(session, device_id) >= limits.MAX_TRIPS_PER_DEVICE
    ):
        raise RuleViolation("device_trip_limit_reached")
    member_id = await _resolve_target_member(
        session, trip.id, trip.closed_at is not None, device_id, choice, now
    )
    if member_id is None:
        return None
    await device_repository.upsert_membership(session, device_id, trip.id, member_id)
    if current is None or current.member_id != member_id:
        events.add_event(session, trip.id, "member_joined", member_id, member_id, now)
    return await trips.get_trip_detail(session, trip.id, member_id)


async def _resolve_target_member(
    session: AsyncSession,
    trip_id: uuid.UUID,
    is_closed: bool,
    device_id: uuid.UUID,
    choice: uuid.UUID | str,
    now: datetime,
) -> uuid.UUID | None:
    if isinstance(choice, str):
        if is_closed:
            raise RuleViolation("trip_closed")
        return (await members.insert_member(session, trip_id, choice)).id
    member = await repository.find_active_member(session, trip_id, choice)
    if member is None:
        return None
    if await repository.is_member_joined(
        session, trip_id, member.id, now, exclude_device_id=device_id
    ):
        raise RuleViolation("member_already_joined")
    return member.id
