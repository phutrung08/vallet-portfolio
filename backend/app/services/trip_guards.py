"""Shared row-locking and active-caller authorization guards for trip writes."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import trips as trip_repository
from app.repositories.models import Trip
from app.services.errors import RuleViolation


def require_open_trip(trip: Trip) -> None:
    """Reject mutations on closed or locked trips."""
    if trip.closed_at is not None:
        raise RuleViolation("trip_closed")
    if trip.locked_at is not None:
        raise RuleViolation("trip_locked")


async def require_active_caller(
    session: AsyncSession, trip_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """Verify ``actor_id`` is still an active member of ``trip_id``."""
    if await trip_repository.find_active_member(session, trip_id, actor_id) is None:
        raise RuleViolation("member_not_active")


async def lock_trip_for_actor(
    session: AsyncSession,
    trip_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    require_open: bool = True,
    exclusive: bool = True,
) -> Trip | None:
    """Lock ``trip_id`` and re-check caller membership under the lock.

    Re-checking after acquiring the row lock prevents TOCTOU privilege races when another
    request simultaneously removes the caller or changes trip lock/closed state.
    """
    trip = (
        await trip_repository.lock_trip(session, trip_id)
        if exclusive
        else await trip_repository.share_lock_trip(session, trip_id)
    )
    if trip is None:
        return None
    await require_active_caller(session, trip_id, actor_id)
    if require_open:
        require_open_trip(trip)
    return trip
