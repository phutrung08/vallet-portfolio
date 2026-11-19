import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Expense, ExpenseShare, Member


async def add_expense(
    session: AsyncSession, expense: Expense, shares: Sequence[ExpenseShare]
) -> None:
    """Insert the expense and its shares; the flush loads the server-set timestamps."""
    session.add(expense)
    session.add_all(shares)
    await session.flush()


async def count_live(session: AsyncSession, trip_id: uuid.UUID) -> int:
    statement = select(func.count()).where(Expense.trip_id == trip_id, Expense.deleted_at.is_(None))
    return int(await session.scalar(statement) or 0)


async def day_totals(session: AsyncSession, trip_id: uuid.UUID) -> Sequence[tuple[date, int, int]]:
    """Return (day, expense count, total amount) per day with live expenses, newest day first."""
    statement = (
        select(Expense.spent_on, func.count(), func.sum(Expense.amount))
        .where(Expense.trip_id == trip_id, Expense.deleted_at.is_(None))
        .group_by(Expense.spent_on)
        .order_by(Expense.spent_on.desc())
    )
    return [(day, count, int(total)) for day, count, total in await session.execute(statement)]


async def category_totals(
    session: AsyncSession, trip_id: uuid.UUID
) -> Sequence[tuple[str, int, int]]:
    """Return (category, expense count, total amount) for live expenses, largest total first."""
    total_expr = func.sum(Expense.amount)
    statement = (
        select(Expense.category, func.count(), total_expr)
        .where(Expense.trip_id == trip_id, Expense.deleted_at.is_(None))
        .group_by(Expense.category)
        .order_by(total_expr.desc(), Expense.category.asc())
    )
    return [
        (category, count, int(total)) for category, count, total in await session.execute(statement)
    ]


async def payer_totals(
    session: AsyncSession, trip_id: uuid.UUID
) -> Sequence[tuple[uuid.UUID | None, int, int]]:
    """Return (paid_by_id or None, expense count, total amount) for live expenses."""
    total_expr = func.sum(Expense.amount)
    statement = (
        select(Expense.paid_by_id, func.count(), total_expr)
        .where(Expense.trip_id == trip_id, Expense.deleted_at.is_(None))
        .group_by(Expense.paid_by_id)
        .order_by(total_expr.desc())
    )
    return [
        (paid_by, count, int(total)) for paid_by, count, total in await session.execute(statement)
    ]


async def list_on_day(session: AsyncSession, trip_id: uuid.UUID, day: date) -> Sequence[Expense]:
    """Return live expenses of one day, newest first."""
    statement = (
        select(Expense)
        .where(Expense.trip_id == trip_id, Expense.spent_on == day, Expense.deleted_at.is_(None))
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )
    return (await session.scalars(statement)).all()


async def shares_of(
    session: AsyncSession, expense_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[ExpenseShare]]:
    """Query the shares of all ``expense_ids``, ordered by member position."""
    if not expense_ids:
        return {}
    statement = (
        select(ExpenseShare)
        .join(
            Member,
            (Member.trip_id == ExpenseShare.trip_id) & (Member.id == ExpenseShare.member_id),
        )
        .where(ExpenseShare.expense_id.in_(expense_ids))
        .order_by(Member.position)
    )
    grouped: dict[uuid.UUID, list[ExpenseShare]] = defaultdict(list)
    for share in await session.scalars(statement):
        grouped[share.expense_id].append(share)
    return grouped


async def live_share_rows(
    session: AsyncSession, trip_id: uuid.UUID
) -> Sequence[tuple[uuid.UUID, uuid.UUID | None, int, uuid.UUID, int]]:
    """Query every live expense with its shares: (expense, payer, amount, member, share)."""
    statement = (
        select(
            Expense.id,
            Expense.paid_by_id,
            Expense.amount,
            ExpenseShare.member_id,
            ExpenseShare.amount,
        )
        .select_from(Expense)
        .join(
            ExpenseShare,
            (ExpenseShare.trip_id == Expense.trip_id) & (ExpenseShare.expense_id == Expense.id),
        )
        .where(Expense.trip_id == trip_id, Expense.deleted_at.is_(None))
    )
    result = await session.execute(statement)
    return [(expense, payer, total, member, part) for expense, payer, total, member, part in result]


async def find_live(
    session: AsyncSession, trip_id: uuid.UUID, expense_id: uuid.UUID
) -> Expense | None:
    """Return the expense if it belongs to the trip and is not deleted."""
    return await session.scalar(_live(trip_id, expense_id))


async def lock_live(
    session: AsyncSession, trip_id: uuid.UUID, expense_id: uuid.UUID
) -> Expense | None:
    """Return the live expense while holding its row lock (FOR UPDATE) until commit."""
    statement = _live(trip_id, expense_id).with_for_update()
    return await session.scalar(statement.execution_options(populate_existing=True))


def _live(trip_id: uuid.UUID, expense_id: uuid.UUID) -> Select[Expense]:
    return select(Expense).where(
        Expense.trip_id == trip_id, Expense.id == expense_id, Expense.deleted_at.is_(None)
    )


async def share_member_ids(session: AsyncSession, expense_id: uuid.UUID) -> set[uuid.UUID]:
    statement = select(ExpenseShare.member_id).where(ExpenseShare.expense_id == expense_id)
    return set(await session.scalars(statement))


async def replace_shares(
    session: AsyncSession, expense_id: uuid.UUID, shares: Sequence[ExpenseShare]
) -> None:
    """Delete the expense's shares, then insert ``shares`` in the caller's transaction."""
    await session.execute(delete(ExpenseShare).where(ExpenseShare.expense_id == expense_id))
    session.add_all(shares)
    await session.flush()
