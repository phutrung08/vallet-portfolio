"""Reading paginated trip activity events."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import events as repository


@dataclass(frozen=True)
class EventView:
    """Single audit log entry safe for member display (no account numbers or tokens)."""

    id: uuid.UUID
    kind: str
    actor_id: uuid.UUID | None
    subject_id: uuid.UUID | None
    created_at: datetime


@dataclass(frozen=True)
class EventPage:
    """Keyset-paginated slice of newest-first trip activity events."""

    events: Sequence[EventView]
    # Cursor for fetching older entries, or None on the final page.
    next_before: uuid.UUID | None


async def list_events(
    session: AsyncSession, trip_id: uuid.UUID, before: uuid.UUID | None, limit: int
) -> EventPage:
    """Return up to ``limit`` activity events older than ``before``, newest first."""
    rows = await repository.list_events(session, trip_id, before, limit + 1)
    page = rows[:limit]
    return EventPage(
        events=[
            EventView(e.id, e.kind, e.actor_member_id, e.subject_member_id, e.created_at)
            for e in page
        ],
        next_before=page[-1].id if len(rows) > limit else None,
    )
