from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Base, Member, Trip
from tests.db.factories import (
    add_trip,
    assert_rejected,
    make_bank_account,
    make_contribution,
    make_device,
    make_event,
    make_expense,
    make_idempotency_key,
    make_member,
    make_payment,
    make_share,
    make_trip,
)

pytestmark = pytest.mark.anyio

type BadRow = Callable[[Trip, list[Member]], Base]

BAD_ROWS: dict[str, tuple[str, BadRow]] = {
    "empty trip name": ("ck_trips_name_length", lambda t, m: make_trip(name="")),
    "whitespace trip name": ("ck_trips_name_length", lambda t, m: make_trip(name="   ")),
    "trip name too long": ("ck_trips_name_length", lambda t, m: make_trip(name="x" * 81)),
    "lowercase currency": ("ck_trips_currency_code", lambda t, m: make_trip(currency="vnd")),
    "short currency": ("ck_trips_currency_code", lambda t, m: make_trip(currency="VN")),
    "ends before starts": (
        "ck_trips_dates_ordered",
        lambda t, m: make_trip(starts_on=date(2026, 3, 2), ends_on=date(2026, 3, 1)),
    ),
    "share hash too short": (
        "ck_trips_share_token_hash_length",
        lambda t, m: make_trip(share_token_hash=b"\x00" * 31),
    ),
    "share token version below 1": (
        "ck_trips_share_token_version_min",
        lambda t, m: make_trip(share_token_version=0),
    ),
    "whitespace member name": (
        "ck_members_display_name_length",
        lambda t, m: make_member(t, 9, display_name=" \t "),
    ),
    "negative position": ("ck_members_position_non_negative", lambda t, m: make_member(t, -1)),
    "empty expense title": (
        "ck_expenses_title_length",
        lambda t, m: make_expense(t, m[0], m[0], title=" "),
    ),
    "negative expense amount": (
        "ck_expenses_amount_non_negative",
        lambda t, m: make_expense(t, m[0], m[0], amount=-1),
    ),
    "unknown category": (
        "ck_expenses_category_known",
        lambda t, m: make_expense(t, m[0], m[0], category="drinks"),
    ),
    "unknown split mode": (
        "ck_expenses_split_mode_known",
        lambda t, m: make_expense(t, m[0], m[0], split_mode="random"),
    ),
    "blank expense note": (
        "ck_expenses_note_length",
        lambda t, m: make_expense(t, m[0], m[0], note="   "),
    ),
    "note too long": (
        "ck_expenses_note_length",
        lambda t, m: make_expense(t, m[0], m[0], note="x" * 501),
    ),
    "blank expense place": (
        "ck_expenses_place_length",
        lambda t, m: make_expense(t, m[0], m[0], place=" \n "),
    ),
    "place too long": (
        "ck_expenses_place_length",
        lambda t, m: make_expense(t, m[0], m[0], place="x" * 201),
    ),
    "expense version below 1": (
        "ck_expenses_version_min",
        lambda t, m: make_expense(t, m[0], m[0], version=0),
    ),
    "zero contribution": (
        "ck_fund_contributions_amount_positive",
        lambda t, m: make_contribution(t, m[0], amount=0),
    ),
    "negative contribution": (
        "ck_fund_contributions_amount_positive",
        lambda t, m: make_contribution(t, m[0], amount=-5),
    ),
    "zero payment": (
        "ck_payments_amount_positive",
        lambda t, m: make_payment(t, m[0], m[1], amount=0),
    ),
    "negative payment": (
        "ck_payments_amount_positive",
        lambda t, m: make_payment(t, m[0], m[1], amount=-1),
    ),
    "payment to oneself": (
        "ck_payments_payer_is_not_payee",
        lambda t, m: make_payment(t, m[0], m[0]),
    ),
    "blank payment note": (
        "ck_payments_note_length",
        lambda t, m: make_payment(t, m[0], m[1], note=" "),
    ),
    "payment note too long": (
        "ck_payments_note_length",
        lambda t, m: make_payment(t, m[0], m[1], note="x" * 201),
    ),
    "short bank bin": (
        "ck_bank_accounts_bank_bin_format",
        lambda t, m: make_bank_account(t, m[0], bank_bin="97043"),
    ),
    "letters in bank bin": (
        "ck_bank_accounts_bank_bin_format",
        lambda t, m: make_bank_account(t, m[0], bank_bin="97043A"),
    ),
    "three digit last4": (
        "ck_bank_accounts_account_last4_format",
        lambda t, m: make_bank_account(t, m[0], account_last4="789"),
    ),
    "five digit last4": (
        "ck_bank_accounts_account_last4_format",
        lambda t, m: make_bank_account(t, m[0], account_last4="56789"),
    ),
    "empty last4": (
        "ck_bank_accounts_account_last4_format",
        lambda t, m: make_bank_account(t, m[0], account_last4=""),
    ),
    "lowercase account name": (
        "ck_bank_accounts_account_name_format",
        lambda t, m: make_bank_account(t, m[0], account_name="Nguyen Van An"),
    ),
    "diacritics in account name": (
        "ck_bank_accounts_account_name_format",
        lambda t, m: make_bank_account(t, m[0], account_name="NGUYỄN"),
    ),
    "empty account name": (
        "ck_bank_accounts_account_name_format",
        lambda t, m: make_bank_account(t, m[0], account_name=""),
    ),
    "account name too long": (
        "ck_bank_accounts_account_name_format",
        lambda t, m: make_bank_account(t, m[0], account_name="A" * 51),
    ),
    "unknown trip event kind": (
        "ck_trip_events_kind_known",
        lambda t, m: make_event(t, kind="unknown_kind", actor=m[0]),
    ),
}


@pytest.mark.parametrize(("constraint", "bad_row"), BAD_ROWS.values(), ids=BAD_ROWS.keys())
async def test_check_constraint_rejects_bad_row(
    session: AsyncSession, constraint: str, bad_row: BadRow
) -> None:
    trip, members = await add_trip(session)

    await assert_rejected(session, constraint, bad_row(trip, members))


async def test_fund_holder_changed_event_is_accepted(session: AsyncSession) -> None:
    trip, (an, binh) = await add_trip(session)
    session.add(make_event(trip, kind="fund_holder_changed", actor=an, subject=binh))
    await session.flush()


async def test_idempotency_key_constraints(session: AsyncSession) -> None:
    device = make_device()
    session.add(device)
    await session.flush()

    await assert_rejected(
        session,
        "ck_idempotency_keys_request_hash_length",
        make_idempotency_key(device, request_hash=b"\x00" * 31),
    )
    await assert_rejected(
        session,
        "ck_idempotency_keys_response_complete",
        make_idempotency_key(device, status_code=201, response_body=None),
    )
    await assert_rejected(
        session,
        "ck_idempotency_keys_response_complete",
        make_idempotency_key(device, status_code=None, response_body={"ok": True}),
    )
    session.add(make_idempotency_key(device, status_code=None, response_body=None))
    await session.flush()


async def test_negative_share_amount_and_weight_are_rejected(session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    expense = make_expense(trip, an, an)
    session.add(expense)
    await session.flush()

    await assert_rejected(
        session, "ck_expense_shares_amount_non_negative", make_share(expense, an, -1)
    )
    await assert_rejected(
        session, "ck_expense_shares_weight_non_negative", make_share(expense, an, 1, weight=-1)
    )


async def test_active_member_names_are_unique_per_trip_ignoring_case(
    session: AsyncSession,
) -> None:
    trip, (an, _) = await add_trip(session)
    an.display_name = "An"
    await session.flush()

    duplicate = make_member(trip, 5, display_name="an")
    await assert_rejected(session, "uq_members_trip_id_lower_display_name", duplicate)

    an.removed_at = datetime.now(UTC)
    session.add(make_member(trip, 6, display_name="an"))
    await session.flush()


async def test_same_member_name_is_allowed_in_another_trip(session: AsyncSession) -> None:
    trip, _ = await add_trip(session)
    other, _ = await add_trip(session)

    session.add_all(
        [make_member(trip, 7, display_name="Hợp"), make_member(other, 7, display_name="Hợp")]
    )
    await session.flush()


async def test_member_position_is_unique_per_trip(session: AsyncSession) -> None:
    trip, _ = await add_trip(session)

    await assert_rejected(session, "uq_members_trip_id_position", make_member(trip, 0))


async def test_one_bank_account_per_member(session: AsyncSession) -> None:
    trip, (an, binh) = await add_trip(session)
    session.add_all([make_bank_account(trip, an), make_bank_account(trip, binh)])
    await session.flush()

    await assert_rejected(session, "pk_bank_accounts", make_bank_account(trip, an))
