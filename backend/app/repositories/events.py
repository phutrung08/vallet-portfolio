import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import EventKind, TripEvent


def add_event(
    session: AsyncSession,
    trip_id: uuid.UUID,
    kind: EventKind,
    actor_id: uuid.UUID | None,
    subject_id: uuid.UUID | None,
    now: datetime,
) -> None:
    """Append to the trip's log in the caller's transaction so it commits atomically."""
    session.add(
        TripEvent(
            id=uuid.uuid4(),
            trip_id=trip_id,
            actor_member_id=actor_id,
            subject_member_id=subject_id,
            kind=kind,
            created_at=now,
        )
    )


async def list_events(
    session: AsyncSession, trip_id: uuid.UUID, before: uuid.UUID | None, limit: int
) -> Sequence[TripEvent]:
    """Return newest events first, optionally paginated strictly older than ``before``."""
    statement = select(TripEvent).where(TripEvent.trip_id == trip_id)
    if before is not None:
        anchor = await session.scalar(
            select(TripEvent).where(TripEvent.trip_id == trip_id, TripEvent.id == before)
        )
        if anchor is None:
            return []
        statement = statement.where(
            tuple_(TripEvent.created_at, TripEvent.id) < tuple_(anchor.created_at, anchor.id)
        )
    statement = statement.order_by(TripEvent.created_at.desc(), TripEvent.id.desc()).limit(limit)
    return (await session.scalars(statement.execution_options(populate_existing=True))).all()


async def latest_bank_account_changes(
    session: AsyncSession, trip_id: uuid.UUID
) -> dict[uuid.UUID, datetime]:
    """Return when each member's bank account last changed (set or removed)."""
    statement = (
        select(TripEvent.subject_member_id, func.max(TripEvent.created_at))
        .where(
            TripEvent.trip_id == trip_id,
            TripEvent.kind.in_(("bank_account_set", "bank_account_removed")),
            TripEvent.subject_member_id.is_not(None),
        )
        .group_by(TripEvent.subject_member_id)
    )
    rows = await session.execute(statement)
    return {member_id: changed_at for member_id, changed_at in rows if member_id is not None}
