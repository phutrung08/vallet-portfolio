import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Payment


def add_payment(session: AsyncSession, payment: Payment) -> None:
    session.add(payment)


async def count_live_payments(session: AsyncSession, trip_id: uuid.UUID) -> int:
    statement = select(func.count()).where(Payment.trip_id == trip_id, Payment.deleted_at.is_(None))
    return int(await session.scalar(statement) or 0)


async def list_live_payments(session: AsyncSession, trip_id: uuid.UUID) -> Sequence[Payment]:
    """Return non-deleted payments newest first in one query."""
    statement = (
        select(Payment)
        .where(Payment.trip_id == trip_id, Payment.deleted_at.is_(None))
        .order_by(Payment.paid_on.desc(), Payment.created_at.desc(), Payment.id.desc())
    )
    return (await session.scalars(statement)).all()


async def lock_live_payment(
    session: AsyncSession, trip_id: uuid.UUID, payment_id: uuid.UUID
) -> Payment | None:
    """Return the live payment held until commit."""
    statement = (
        select(Payment)
        .where(
            Payment.trip_id == trip_id,
            Payment.id == payment_id,
            Payment.deleted_at.is_(None),
        )
        .with_for_update()
    )
    return await session.scalar(statement.execution_options(populate_existing=True))
