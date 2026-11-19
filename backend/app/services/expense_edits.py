"""Editing and soft-deleting recorded expenses with optimistic concurrency control."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.repositories import expenses as repository
from app.repositories import trips as trip_repository
from app.repositories.models import Expense, Trip
from app.services.errors import RuleViolation
from app.services.expenses import (
    ExpenseDetail,
    NewExpense,
    build_shares,
    compute_split,
    expense_detail,
    member_positions,
    order_by_position,
    require_payer,
)
from app.services.trip_guards import lock_trip_for_actor


async def _lock_for_change(
    session: AsyncSession, trip_id: uuid.UUID, expense_id: uuid.UUID, actor_id: uuid.UUID
) -> tuple[Trip, Expense] | None:
    """Acquire shared trip lock (after active-caller check), then lock the target expense row."""
    trip = await lock_trip_for_actor(session, trip_id, actor_id, require_open=True, exclusive=False)
    if trip is None:
        return None
    expense = await repository.lock_live(session, trip_id, expense_id)
    return None if expense is None else (trip, expense)


def _stamp(expense: Expense, editor_id: uuid.UUID, now: datetime) -> None:
    expense.updated_by_id = editor_id
    expense.updated_at = now
    # Always mark dirty so column onupdate does not leave updated_at expired in async sessions.
    flag_modified(expense, "updated_at")


def _apply(expense: Expense, data: NewExpense, editor_id: uuid.UUID, now: datetime) -> None:
    expense.title = data.title
    expense.amount = data.amount
    expense.category = data.category
    expense.spent_on = data.spent_on
    expense.paid_by_id = data.paid_by
    expense.note = data.note
    expense.place = data.place
    expense.split_mode = data.split_mode
    expense.version += 1
    _stamp(expense, editor_id, now)


async def edit_expense(
    session: AsyncSession,
    trip_id: uuid.UUID,
    expense_id: uuid.UUID,
    editor_id: uuid.UUID,
    data: NewExpense,
    expected_version: int,
    now: datetime,
) -> ExpenseDetail | None:
    """Replace an expense and its shares, or return None if the trip or live expense is absent.

    ``expected_version`` enforces optimistic locking under the row lock: a stale edit fails
    with ``version_conflict``. Removed members may remain payer or participant only if they
    already appeared on this expense.
    """
    locked = await _lock_for_change(session, trip_id, expense_id, editor_id)
    if locked is None:
        return None
    trip, expense = locked
    if expense.version != expected_version:
        raise RuleViolation("version_conflict")
    members = await trip_repository.list_members(session, trip_id)
    previous = await repository.share_member_ids(session, expense_id)
    if expense.paid_by_id is not None:
        previous.add(expense.paid_by_id)
    allowed = member_positions(members, previous)
    require_payer(trip, data.paid_by, allowed)
    ordered = order_by_position(data.weights, allowed)
    parts = compute_split(data.split_mode, data.amount, ordered)
    _apply(expense, data, editor_id, now)
    shares = build_shares(expense, ordered, parts)
    await repository.replace_shares(session, expense_id, shares)
    return expense_detail(expense, shares)


async def delete_expense(
    session: AsyncSession,
    trip_id: uuid.UUID,
    expense_id: uuid.UUID,
    editor_id: uuid.UUID,
    now: datetime,
) -> bool:
    """Soft-delete a live expense; return False when the trip or live expense is absent."""
    locked = await _lock_for_change(session, trip_id, expense_id, editor_id)
    if locked is None:
        return False
    _, expense = locked
    expense.deleted_at = now
    _stamp(expense, editor_id, now)
    return True
