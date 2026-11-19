"""Reading recorded expenses: daily totals, expenses on a day, and single expense detail."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import expenses as repository
from app.services.expenses import ExpenseDetail, expense_detail


@dataclass(frozen=True)
class DaySummary:
    """Aggregated expense count and total amount for one trip day."""

    date: date
    count: int
    total: int


async def list_days(session: AsyncSession, trip_id: uuid.UUID) -> list[DaySummary]:
    """Return live daily totals ordered newest day first."""
    return [DaySummary(*row) for row in await repository.day_totals(session, trip_id)]


async def list_day(session: AsyncSession, trip_id: uuid.UUID, day: date) -> list[ExpenseDetail]:
    """Fetch one day's expenses and their shares in two constant queries."""
    rows = await repository.list_on_day(session, trip_id, day)
    shares = await repository.shares_of(session, [row.id for row in rows])
    return [expense_detail(row, shares[row.id]) for row in rows]


async def get_expense(
    session: AsyncSession, trip_id: uuid.UUID, expense_id: uuid.UUID
) -> ExpenseDetail | None:
    """Return a single live expense and its ordered shares, or None when absent."""
    row = await repository.find_live(session, trip_id, expense_id)
    if row is None:
        return None
    shares = await repository.shares_of(session, [row.id])
    return expense_detail(row, shares[row.id])
