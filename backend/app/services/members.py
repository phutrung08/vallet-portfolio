"""Managing a trip's members with post-lock active-caller verification."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.repositories import devices as device_repository
from app.repositories import events
from app.repositories import trips as repository
from app.repositories.models import Member
from app.services.errors import RuleViolation
from app.services.names import has_duplicate_names
from app.services.trip_guards import lock_trip_for_actor
from app.services.trips import MemberView, member_view


async def insert_member(session: AsyncSession, trip_id: uuid.UUID, name: str) -> Member:
    """Create a new member at the next position while the caller holds the trip row lock."""
    members = await repository.list_members(session, trip_id)
    if len(members) >= limits.MAX_TOTAL_MEMBERS:
        raise RuleViolation("trip_full")
    active_names = [m.display_name for m in members if m.removed_at is None]
    if len(active_names) >= limits.MAX_ACTIVE_MEMBERS:
        raise RuleViolation("trip_full")
    if has_duplicate_names([*active_names, name]):
        raise RuleViolation("name_taken")
    # Over removed members too: positions are never reused.
    position = max((m.position for m in members), default=-1) + 1
    member = Member(id=uuid.uuid4(), trip_id=trip_id, display_name=name, position=position)
    repository.add_member(session, member)
    return member


async def add_member(
    session: AsyncSession, trip_id: uuid.UUID, actor_id: uuid.UUID, name: str, now: datetime
) -> MemberView | None:
    """Add a new member to an open trip and append an activity event."""
    if await lock_trip_for_actor(session, trip_id, actor_id, require_open=True) is None:
        return None
    member = await insert_member(session, trip_id, name)
    events.add_event(session, trip_id, "member_added", actor_id, member.id, now)
    return member_view(member)


async def rename_member(
    session: AsyncSession,
    trip_id: uuid.UUID,
    actor_id: uuid.UUID,
    member_id: uuid.UUID,
    name: str,
    now: datetime,
) -> MemberView | None:
    """Rename an active member of an open trip; None when the trip or target is absent."""
    if await lock_trip_for_actor(session, trip_id, actor_id, require_open=True) is None:
        return None
    members = await repository.list_members(session, trip_id)
    target = next((m for m in members if m.id == member_id and m.removed_at is None), None)
    if target is None:
        return None
    other_names = [m.display_name for m in members if m.removed_at is None and m.id != member_id]
    if has_duplicate_names([*other_names, name]):
        raise RuleViolation("name_taken")
    target.display_name = name
    events.add_event(session, trip_id, "member_renamed", actor_id, member_id, now)
    return member_view(target)


async def remove_member(
    session: AsyncSession,
    trip_id: uuid.UUID,
    actor_id: uuid.UUID,
    member_id: uuid.UUID,
    now: datetime,
) -> bool:
    """Soft-remove a member and revoke its devices; False when the trip or member is absent."""
    trip = await lock_trip_for_actor(session, trip_id, actor_id, require_open=True)
    if trip is None:
        return False
    members = await repository.list_members(session, trip_id)
    target = next((m for m in members if m.id == member_id and m.removed_at is None), None)
    if target is None:
        return False
    if trip.fund_holder_id == member_id:
        raise RuleViolation("member_is_fund_holder")
    if sum(m.removed_at is None for m in members) <= 1:
        raise RuleViolation("last_member")
    target.removed_at = now
    await device_repository.revoke_member_memberships(session, trip_id, member_id, now)
    events.add_event(session, trip_id, "member_removed", actor_id, member_id, now)
    return True


async def leave_trip(
    session: AsyncSession,
    device_id: uuid.UUID,
    trip_id: uuid.UUID,
    member_id: uuid.UUID,
    now: datetime,
) -> None:
    """Revoke only this device's membership in ``trip_id``."""
    if await device_repository.revoke_membership(session, device_id, trip_id, now):
        events.add_event(session, trip_id, "member_left", member_id, member_id, now)
