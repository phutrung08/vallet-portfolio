import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Expense, FundContribution


def add_contribution(session: AsyncSession, contribution: FundContribution) -> None:
    session.add(contribution)


async def count_live_contributions(session: AsyncSession, trip_id: uuid.UUID) -> int:
    statement = select(func.count()).where(
        FundContribution.trip_id == trip_id, FundContribution.deleted_at.is_(None)
    )
    return int(await session.scalar(statement) or 0)


async def list_live_contributions(
    session: AsyncSession, trip_id: uuid.UUID
) -> Sequence[FundContribution]:
    """Return contributions that are not deleted, newest first."""
    statement = (
        select(FundContribution)
        .where(FundContribution.trip_id == trip_id, FundContribution.deleted_at.is_(None))
        .order_by(FundContribution.created_at.desc(), FundContribution.id.desc())
    )
    return (await session.scalars(statement)).all()


async def lock_live_contribution(
    session: AsyncSession, trip_id: uuid.UUID, contribution_id: uuid.UUID
) -> FundContribution | None:
    """Return the live contribution held until commit."""
    statement = (
        select(FundContribution)
        .where(
            FundContribution.trip_id == trip_id,
            FundContribution.id == contribution_id,
            FundContribution.deleted_at.is_(None),
        )
        .with_for_update()
    )
    return await session.scalar(statement.execution_options(populate_existing=True))


async def fund_spent(session: AsyncSession, trip_id: uuid.UUID) -> int:
    """Return total of live expenses paid from the fund."""
    statement = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        *_live_fund_expense(trip_id)
    )
    return int(await session.scalar(statement) or 0)


async def has_live_fund_activity(session: AsyncSession, trip_id: uuid.UUID) -> bool:
    """Return whether any live contribution or live fund-paid expense exists."""
    contribution = exists().where(
        FundContribution.trip_id == trip_id, FundContribution.deleted_at.is_(None)
    )
    expense = exists().where(*_live_fund_expense(trip_id))
    return bool(await session.scalar(select(contribution | expense)))


def _live_fund_expense(trip_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
    return (
        Expense.trip_id == trip_id,
        Expense.paid_by_id.is_(None),
        Expense.deleted_at.is_(None),
    )
