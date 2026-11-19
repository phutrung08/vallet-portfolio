"""Shared fund management: contributions, overview, and custodian holder transitions."""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.repositories import events
from app.repositories import fund as repository
from app.repositories import trips as trip_repository
from app.repositories.models import FundContribution, Member, Trip
from app.services.errors import RuleViolation
from app.services.expenses import member_positions, require_capacity
from app.services.trip_guards import lock_trip_for_actor


@dataclass(frozen=True)
class MemberContribution:
    """Net total contributed by one trip member."""

    member_id: uuid.UUID
    contributed: int


@dataclass(frozen=True)
class ContributionView:
    """Serialized shared fund contribution entry."""

    id: uuid.UUID
    member_id: uuid.UUID
    amount: int
    contributed_on: date
    created_by: uuid.UUID
    created_at: datetime


@dataclass(frozen=True)
class FundSummary:
    """Current fund holder, totals, per-member contributions, and contribution log."""

    holder_id: uuid.UUID | None
    contributed: int
    spent: int
    remaining: int
    members: Sequence[MemberContribution]
    contributions: Sequence[ContributionView]


def _contribution_view(contribution: FundContribution) -> ContributionView:
    return ContributionView(
        id=contribution.id,
        member_id=contribution.member_id,
        amount=contribution.amount,
        contributed_on=contribution.contributed_on,
        created_by=contribution.created_by_id,
        created_at=contribution.created_at,
    )


def _member_totals(
    members: Sequence[Member], contributions: Sequence[FundContribution]
) -> list[MemberContribution]:
    """List every active member by position, plus removed members who have contributions."""
    totals: dict[uuid.UUID, int] = defaultdict(int)
    for contribution in contributions:
        totals[contribution.member_id] += contribution.amount
    shown = member_positions(members, totals.keys())
    return [MemberContribution(m.id, totals.get(m.id, 0)) for m in members if m.id in shown]


async def _summary(session: AsyncSession, trip: Trip) -> FundSummary:
    """Fetch fund state in three constant queries: members, contributions, total spent."""
    members = await trip_repository.list_members(session, trip.id)
    contributions = await repository.list_live_contributions(session, trip.id)
    spent = await repository.fund_spent(session, trip.id)
    contributed = sum(c.amount for c in contributions)
    return FundSummary(
        holder_id=trip.fund_holder_id,
        contributed=contributed,
        spent=spent,
        remaining=contributed - spent,
        members=_member_totals(members, contributions),
        contributions=[_contribution_view(c) for c in contributions],
    )


async def get_summary(session: AsyncSession, trip_id: uuid.UUID) -> FundSummary | None:
    """Return the fund overview for ``trip_id``, or None when the trip does not exist."""
    trip = await trip_repository.find_trip(session, trip_id)
    return None if trip is None else await _summary(session, trip)


async def add_contribution(
    session: AsyncSession,
    trip_id: uuid.UUID,
    author_id: uuid.UUID,
    member_id: uuid.UUID,
    amount: int,
    contributed_on: date,
    now: datetime,
) -> ContributionView | None:
    """Record a contribution to an open trip's shared fund, or return None if absent."""
    # Exclusive lock prevents concurrent writes from overtaking MAX_LIVE_CONTRIBUTIONS.
    trip = await lock_trip_for_actor(session, trip_id, author_id, require_open=True, exclusive=True)
    if trip is None:
        return None
    if trip.fund_holder_id is None:
        raise RuleViolation("no_fund")
    live = await repository.count_live_contributions(session, trip_id)
    require_capacity(live, limits.MAX_LIVE_CONTRIBUTIONS)
    active = member_positions(await trip_repository.list_members(session, trip_id))
    if member_id not in active:
        raise RuleViolation("member_not_active")
    contribution = FundContribution(
        id=uuid.uuid4(),
        trip_id=trip_id,
        member_id=member_id,
        amount=amount,
        contributed_on=contributed_on,
        created_by_id=author_id,
        created_at=now,
    )
    repository.add_contribution(session, contribution)
    return _contribution_view(contribution)


async def delete_contribution(
    session: AsyncSession,
    trip_id: uuid.UUID,
    actor_id: uuid.UUID,
    contribution_id: uuid.UUID,
    now: datetime,
) -> bool:
    """Soft-delete a live contribution after post-lock active-caller verification."""
    if (
        await lock_trip_for_actor(session, trip_id, actor_id, require_open=True, exclusive=False)
        is None
    ):
        return False
    contribution = await repository.lock_live_contribution(session, trip_id, contribution_id)
    if contribution is None:
        return False
    contribution.deleted_at = now
    return True


async def set_holder(
    session: AsyncSession,
    trip_id: uuid.UUID,
    actor_id: uuid.UUID,
    holder_id: uuid.UUID | None,
    now: datetime,
) -> FundSummary | None:
    """Enable, disable, or transfer custody of the shared fund on an open trip."""
    trip = await lock_trip_for_actor(session, trip_id, actor_id, require_open=True, exclusive=True)
    if trip is None:
        return None
    if holder_id is None:
        if await repository.has_live_fund_activity(session, trip_id):
            raise RuleViolation("fund_in_use")
    elif await trip_repository.find_active_member(session, trip_id, holder_id) is None:
        raise RuleViolation("member_not_active")
    if trip.fund_holder_id != holder_id:
        trip.fund_holder_id = holder_id
        events.add_event(session, trip_id, "fund_holder_changed", actor_id, holder_id, now)
    return await _summary(session, trip)
