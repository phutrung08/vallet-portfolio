"""Recording expenses; the server computes every share and client amounts are only checked."""

import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.domain.constants import EXPENSE_CATEGORIES
from app.domain.split import (
    SplitError,
    split_by_percent,
    split_by_shares,
    split_equal,
    split_exact,
)
from app.repositories import expenses as repository
from app.repositories import trips as trip_repository
from app.repositories.models import Expense, ExpenseShare, Member, Trip
from app.services.errors import RuleViolation
from app.services.trip_guards import lock_trip_for_actor

type Splitter = Callable[[int, Mapping[str, int]], dict[str, int]]

__all__ = [
    "EXPENSE_CATEGORIES",
    "ExpenseDetail",
    "NewExpense",
    "ShareView",
    "build_shares",
    "compute_split",
    "create_expense",
    "expense_detail",
    "member_positions",
    "order_by_position",
    "require_capacity",
    "require_payer",
]

# Keyed by split mode. Every splitter takes per-member weights; equal mode weighs everyone 1.
_SPLITTERS: dict[str, Splitter] = {
    "equal": lambda total, weights: split_equal(total, list(weights)),
    "shares": split_by_shares,
    "percent": split_by_percent,
    "exact": split_exact,
}


@dataclass(frozen=True)
class NewExpense:
    """Validated expense write payload passed into the expense service."""

    title: str
    amount: int
    category: str
    spent_on: date
    paid_by: uuid.UUID | None
    split_mode: str
    # Per member: 1 (equal), share count (shares), basis points (percent) or amount (exact).
    weights: Mapping[uuid.UUID, int]
    note: str | None
    place: str | None


@dataclass(frozen=True)
class ShareView:
    """Single participant share in a serialized expense."""

    member_id: uuid.UUID
    weight: int
    amount: int


@dataclass(frozen=True)
class ExpenseDetail:
    """Full expense view returned by expense read and write services."""

    id: uuid.UUID
    title: str
    amount: int
    category: str
    spent_on: date
    paid_by: uuid.UUID | None
    split_mode: str
    shares: Sequence[ShareView]
    note: str | None
    place: str | None
    created_by: uuid.UUID
    updated_by: uuid.UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


def expense_detail(expense: Expense, shares: Sequence[ExpenseShare]) -> ExpenseDetail:
    """Build the API view of an expense; ``shares`` must already be in member position order."""
    return ExpenseDetail(
        id=expense.id,
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        spent_on=expense.spent_on,
        paid_by=expense.paid_by_id,
        split_mode=expense.split_mode,
        shares=[ShareView(s.member_id, s.weight, s.amount) for s in shares],
        note=expense.note,
        place=expense.place,
        created_by=expense.created_by_id,
        updated_by=expense.updated_by_id,
        version=expense.version,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


def order_by_position(
    weights: Mapping[uuid.UUID, int], positions: Mapping[uuid.UUID, int]
) -> dict[uuid.UUID, int]:
    """Re-key ``weights`` in member position order so remainders never depend on JSON key order.

    ``positions`` holds allowed members only; any unknown or removed ID raises
    ``member_not_active`` uniformly without revealing membership status.
    """
    if not weights.keys() <= positions.keys():
        raise RuleViolation("member_not_active")
    return {member: weights[member] for member in sorted(weights, key=positions.__getitem__)}


def compute_split(mode: str, amount: int, ordered: Mapping[uuid.UUID, int]) -> list[int]:
    """Compute each member's split share of ``amount`` in the order of ``ordered``."""
    try:
        parts = _SPLITTERS[mode](amount, {str(member): w for member, w in ordered.items()})
    except SplitError as error:
        # Domain errors embed member IDs; expose only the rule code and exact gap.
        difference = amount - sum(ordered.values()) if mode == "exact" else None
        raise RuleViolation("invalid_split", difference=difference) from error
    return [parts[str(member)] for member in ordered]


def require_capacity(live: int, limit: int) -> None:
    """Refuse adding another row once the trip already holds ``limit`` live rows."""
    if live >= limit:
        raise RuleViolation("trip_limit_reached")


def require_payer(trip: Trip, paid_by: uuid.UUID | None, active: Mapping[uuid.UUID, int]) -> None:
    """Validate that ``paid_by`` is an allowed member or an active shared fund."""
    if paid_by is None:
        if trip.fund_holder_id is None:
            raise RuleViolation("no_fund")
    elif paid_by not in active:
        raise RuleViolation("member_not_active")


def member_positions(
    members: Sequence[Member], keep: Collection[uuid.UUID] = ()
) -> dict[uuid.UUID, int]:
    """Return positions of active members plus any removed member whose ID is in ``keep``."""
    return {m.id: m.position for m in members if m.removed_at is None or m.id in keep}


def build_shares(
    expense: Expense, ordered: Mapping[uuid.UUID, int], parts: Sequence[int]
) -> list[ExpenseShare]:
    """Construct ``ExpenseShare`` rows pairing ordered member weights with computed amounts."""
    return [
        ExpenseShare(
            expense_id=expense.id, member_id=m, trip_id=expense.trip_id, weight=w, amount=part
        )
        for (m, w), part in zip(ordered.items(), parts, strict=True)
    ]


async def create_expense(
    session: AsyncSession, trip_id: uuid.UUID, author_id: uuid.UUID, data: NewExpense
) -> ExpenseDetail | None:
    """Record a new expense on an open trip, or return None when the trip does not exist."""
    # Exclusive lock prevents concurrent creates from racing past MAX_LIVE_EXPENSES.
    trip = await lock_trip_for_actor(session, trip_id, author_id, require_open=True, exclusive=True)
    if trip is None:
        return None
    require_capacity(await repository.count_live(session, trip_id), limits.MAX_LIVE_EXPENSES)
    active = member_positions(await trip_repository.list_members(session, trip_id))
    require_payer(trip, data.paid_by, active)
    ordered = order_by_position(data.weights, active)
    parts = compute_split(data.split_mode, data.amount, ordered)
    expense = Expense(
        id=uuid.uuid4(),
        trip_id=trip_id,
        title=data.title,
        amount=data.amount,
        paid_by_id=data.paid_by,
        category=data.category,
        spent_on=data.spent_on,
        note=data.note,
        place=data.place,
        split_mode=data.split_mode,
        created_by_id=author_id,
        updated_by_id=None,
        version=1,
    )
    shares = build_shares(expense, ordered, parts)
    await repository.add_expense(session, expense, shares)
    return expense_detail(expense, shares)
