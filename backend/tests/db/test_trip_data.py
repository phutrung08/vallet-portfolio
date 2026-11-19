from datetime import date

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import (
    Expense,
    ExpenseShare,
    FundContribution,
    Member,
    Payment,
    Trip,
)
from tests.db.factories import (
    add_trip,
    check_deferred_constraints,
    make_contribution,
    make_expense,
    make_payment,
    make_share,
)

pytestmark = pytest.mark.anyio


async def add_full_trip(session: AsyncSession) -> Trip:
    """A trip with three members, a fund held by the first, and both kinds of expense."""
    trip, (an, binh, chi) = await add_trip(session, member_count=3)
    trip.fund_holder_id = an.id
    by_member = make_expense(trip, binh, binh, amount=300_000)
    from_fund = make_expense(trip, None, an, title="Ferry tickets", amount=150_000)
    session.add_all([by_member, from_fund])
    await session.flush()
    session.add_all(
        [
            make_share(by_member, an, 100_000),
            make_share(by_member, binh, 100_000),
            make_share(by_member, chi, 100_000),
            make_share(from_fund, an, 75_000, weight=5_000),
            make_share(from_fund, chi, 75_000, weight=5_000),
            make_contribution(trip, an, amount=200_000),
            make_contribution(trip, chi, amount=200_000, created_by_id=an.id),
            make_payment(trip, chi, binh, note="Settled dinner share", created_by_id=an.id),
        ]
    )
    await session.flush()
    return trip


async def test_trip_round_trips_through_the_database(session: AsyncSession) -> None:
    trip = await add_full_trip(session)
    session.expunge_all()

    stored = await session.get_one(Trip, trip.id)
    members = (await session.scalars(select(Member).order_by(Member.position))).all()
    expenses = (await session.scalars(select(Expense).order_by(Expense.amount))).all()
    shares = (await session.scalars(select(ExpenseShare))).all()
    contributions = (await session.scalars(select(FundContribution))).all()
    payments = (await session.scalars(select(Payment))).all()

    assert stored.currency == "VND"
    assert stored.created_at is not None
    assert stored.fund_holder_id == members[0].id
    assert [m.display_name for m in members] == ["Member 0", "Member 1", "Member 2"]
    assert [(e.amount, e.paid_by_id) for e in expenses] == [
        (150_000, None),
        (300_000, members[1].id),
    ]
    assert all(e.spent_on == date(2026, 3, 1) and e.deleted_at is None for e in expenses)
    assert sorted(s.amount for s in shares) == [75_000, 75_000, 100_000, 100_000, 100_000]
    assert sum(c.amount for c in contributions) == 400_000
    assert [(p.payer_id, p.payee_id, p.amount, p.note) for p in payments] == [
        (members[2].id, members[1].id, 100_000, "Settled dinner share")
    ]
    assert payments[0].created_at is not None and payments[0].deleted_at is None


async def test_deleting_a_trip_cascades_to_all_its_rows(session: AsyncSession) -> None:
    trip = await add_full_trip(session)
    other, _ = await add_trip(session)

    await session.execute(delete(Trip).where(Trip.id == trip.id))
    await check_deferred_constraints(session)

    for model in (Member, Expense, ExpenseShare, FundContribution, Payment):
        remaining = await session.scalar(
            select(func.count()).select_from(model).where(model.trip_id == trip.id)
        )
        assert remaining == 0, model.__tablename__
    other_members = select(func.count()).where(Member.trip_id == other.id)
    assert await session.scalar(other_members) == 2


async def test_hard_deleting_a_referenced_member_is_rejected(session: AsyncSession) -> None:
    trip = await add_full_trip(session)
    holder = await session.get_one(Member, trip.fund_holder_id)

    with pytest.raises(IntegrityError, match="fk_.*_members"):
        async with session.begin_nested():
            await session.delete(holder)
            await check_deferred_constraints(session)
