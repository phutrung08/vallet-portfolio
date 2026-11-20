"""Aggregated trip spend summary computed server-side in SQL and exact integer arithmetic."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.money import allocate
from app.repositories import expenses as expense_repository
from app.repositories import trips as trip_repository


@dataclass(frozen=True)
class CategoryBreakdown:
    """Spending total and whole-percent share for one expense category."""

    category: str
    count: int
    amount: int
    percent: int


@dataclass(frozen=True)
class PayerBreakdown:
    """Total amount and expense count paid by one member or the shared fund (``None``)."""

    paid_by: uuid.UUID | None
    count: int
    amount: int


@dataclass(frozen=True)
class DayBreakdown:
    """Expense count and spend total for one trip day."""

    date: date
    count: int
    total: int


@dataclass(frozen=True)
class TripSummaryReport:
    """Complete aggregated spending breakdown for a trip."""

    currency: str
    total: int
    expense_count: int
    active_member_count: int
    day_count: int
    per_person: int
    per_day: int
    categories: Sequence[CategoryBreakdown]
    payers: Sequence[PayerBreakdown]
    days: Sequence[DayBreakdown]


def _round_half_up(total: int, count: int) -> int:
    """Divide ``total`` by ``count`` rounding halves upward in pure integer math."""
    if count <= 0:
        return 0
    return (total * 2 + count) // (2 * count)


async def get_trip_summary(session: AsyncSession, trip_id: uuid.UUID) -> TripSummaryReport | None:
    """Aggregate trip spend, categories, payers, and days in four constant SQL queries."""
    found = await trip_repository.find_trip_with_members(session, trip_id)
    if found is None:
        return None
    trip, members = found
    day_rows = await expense_repository.day_totals(session, trip_id)
    cat_rows = await expense_repository.category_totals(session, trip_id)
    payer_rows = await expense_repository.payer_totals(session, trip_id)

    total = sum(row_total for _, _, row_total in day_rows)
    expense_count = sum(row_count for _, row_count, _ in day_rows)
    active_member_count = sum(m.removed_at is None for m in members)
    day_count = len(day_rows)

    percents = allocate(100, [amount for _, _, amount in cat_rows]) if cat_rows else []
    categories = [
        CategoryBreakdown(category=category, count=count, amount=amount, percent=percent)
        for (category, count, amount), percent in zip(cat_rows, percents, strict=True)
    ]
    sorted_payers = sorted(
        payer_rows,
        key=lambda row: (-row[2], row[0] is None, str(row[0] or "")),
    )
    payers = [
        PayerBreakdown(paid_by=paid_by, count=count, amount=amount)
        for paid_by, count, amount in sorted_payers
    ]
    days = [
        DayBreakdown(date=day, count=count, total=row_total) for day, count, row_total in day_rows
    ]

    return TripSummaryReport(
        currency=trip.currency,
        total=total,
        expense_count=expense_count,
        active_member_count=active_member_count,
        day_count=day_count,
        per_person=_round_half_up(total, active_member_count),
        per_day=_round_half_up(total, day_count),
        categories=categories,
        payers=payers,
        days=days,
    )
