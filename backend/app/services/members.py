"""Managing a trip's members."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.repositories import trips as repository
from app.repositories.models import Member
from app.services.errors import RuleViolation
from app.services.names import has_duplicate_names


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
