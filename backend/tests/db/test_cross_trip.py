"""Composite foreign keys must stop any row from pointing at a member of another trip."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.db.factories import (
    add_trip,
    assert_rejected,
    check_deferred_constraints,
    make_bank_account,
    make_contribution,
    make_device,
    make_event,
    make_expense,
    make_membership,
    make_payment,
    make_share,
)

pytestmark = pytest.mark.anyio


async def test_expense_paid_by_member_of_another_trip_is_rejected(session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    await assert_rejected(
        session, "fk_expenses_trip_id_paid_by_id_members", make_expense(trip, outsider, an)
    )


async def test_expense_created_by_member_of_another_trip_is_rejected(
    session: AsyncSession,
) -> None:
    trip, (an, _) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    await assert_rejected(
        session, "fk_expenses_trip_id_created_by_id_members", make_expense(trip, an, outsider)
    )


async def test_expense_updated_by_member_of_another_trip_is_rejected(
    session: AsyncSession,
) -> None:
    trip, (an, _) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    expense = make_expense(trip, an, an, updated_by_id=outsider.id)
    await assert_rejected(session, "fk_expenses_trip_id_updated_by_id_members", expense)


async def test_share_for_member_of_another_trip_is_rejected(session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)
    expense = make_expense(trip, an, an)
    session.add(expense)
    await session.flush()

    await assert_rejected(
        session, "fk_expense_shares_trip_id_member_id_members", make_share(expense, outsider, 1)
    )


async def test_share_whose_trip_disagrees_with_its_expense_is_rejected(
    session: AsyncSession,
) -> None:
    trip, (an, _) = await add_trip(session)
    other, (outsider, _) = await add_trip(session)
    expense = make_expense(trip, an, an)
    session.add(expense)
    await session.flush()

    share = make_share(expense, outsider, 1, trip_id=other.id)
    await assert_rejected(session, "fk_expense_shares_trip_id_expense_id_expenses", share)


async def test_contribution_by_member_of_another_trip_is_rejected(session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    await assert_rejected(
        session,
        "fk_fund_contributions_trip_id_member_id_members",
        make_contribution(trip, outsider, created_by_id=an.id),
    )
    await assert_rejected(
        session,
        "fk_fund_contributions_trip_id_created_by_id_members",
        make_contribution(trip, an, created_by_id=outsider.id),
    )


@pytest.mark.parametrize("column", ["payer_id", "payee_id", "created_by_id"])
async def test_payment_naming_a_member_of_another_trip_is_rejected(
    session: AsyncSession, column: str
) -> None:
    trip, (an, binh) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    payment = make_payment(trip, an, binh, **{column: outsider.id})
    await assert_rejected(session, f"fk_payments_trip_id_{column}_members", payment)


async def test_bank_account_for_a_member_of_another_trip_is_rejected(
    session: AsyncSession,
) -> None:
    trip, _ = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    await assert_rejected(
        session,
        "fk_bank_accounts_trip_id_member_id_members",
        make_bank_account(trip, outsider),
    )


async def test_membership_for_a_member_of_another_trip_is_rejected(
    session: AsyncSession,
) -> None:
    trip, _ = await add_trip(session)
    _, (outsider, _) = await add_trip(session)
    device = make_device()
    session.add(device)
    await session.flush()

    await assert_rejected(
        session,
        "fk_memberships_trip_id_member_id_members",
        make_membership(device, outsider, trip_id=trip.id),
    )


async def test_trip_event_for_member_of_another_trip_is_rejected(session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    await assert_rejected(
        session,
        "fk_trip_events_trip_id_actor_member_id_members",
        make_event(trip, actor=outsider, subject=an),
    )
    await assert_rejected(
        session,
        "fk_trip_events_trip_id_subject_member_id_members",
        make_event(trip, actor=an, subject=outsider),
    )


async def test_fund_holder_from_another_trip_is_rejected(session: AsyncSession) -> None:
    trip, _ = await add_trip(session)
    _, (outsider, _) = await add_trip(session)

    with pytest.raises(IntegrityError, match="fk_trips_id_fund_holder_id_members"):
        async with session.begin_nested():
            trip.fund_holder_id = outsider.id
            await check_deferred_constraints(session)
