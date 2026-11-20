from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession, TripMember
from app.api.schemas.events import EventListOut
from app.services import events

router = APIRouter(prefix="/trips/{trip_id}", tags=["events"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@router.get("/events")
async def list_events(
    caller: TripMember,
    session: DbSession,
    before: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> EventListOut:
    """List keyset-paginated activity log entries, newest first."""
    page = await events.list_events(session, caller.trip_id, before, limit)
    return EventListOut.model_validate(page)
