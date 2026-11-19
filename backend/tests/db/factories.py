import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import (
    BankAccount,
    Base,
    Device,
    EventKind,
    Expense,
    ExpenseShare,
    FundContribution,
    IdempotencyKey,
    Member,
    Membership,
    Payment,
    Trip,
    TripEvent,
)


def make_trip(**overrides: Any) -> Trip:
    token_hash = hashlib.sha256(secrets.token_urlsafe(32).encode()).digest()
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "Phu Quoc",
        "share_token_hash": token_hash,
    }
    return Trip(**(fields | overrides))


def make_member(trip: Trip, position: int, **overrides: Any) -> Member:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "trip_id": trip.id,
        "display_name": f"Member {position}",
        "position": position,
    }
    return Member(**(fields | overrides))


def make_expense(trip: Trip, payer: Member | None, author: Member, **overrides: Any) -> Expense:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "trip_id": trip.id,
        "title": "Group dinner",
        "amount": 300_000,
        "paid_by_id": payer.id if payer else None,
        "category": "food",
        "spent_on": date(2026, 3, 1),
        "split_mode": "equal",
        "created_by_id": author.id,
    }
    return Expense(**(fields | overrides))


def make_share(expense: Expense, member: Member, amount: int, **overrides: Any) -> ExpenseShare:
    fields: dict[str, Any] = {
        "expense_id": expense.id,
        "member_id": member.id,
        "trip_id": expense.trip_id,
        "weight": 1,
        "amount": amount,
    }
    return ExpenseShare(**(fields | overrides))


def make_contribution(trip: Trip, member: Member, **overrides: Any) -> FundContribution:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "trip_id": trip.id,
        "member_id": member.id,
        "amount": 500_000,
        "contributed_on": date(2026, 3, 1),
        "created_by_id": member.id,
    }
    return FundContribution(**(fields | overrides))


def make_payment(trip: Trip, payer: Member, payee: Member, **overrides: Any) -> Payment:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "trip_id": trip.id,
        "payer_id": payer.id,
        "payee_id": payee.id,
        "amount": 100_000,
        "paid_on": date(2026, 3, 4),
        "created_by_id": payer.id,
    }
    return Payment(**(fields | overrides))


def make_bank_account(trip: Trip, member: Member, **overrides: Any) -> BankAccount:
    fields: dict[str, Any] = {
        "trip_id": trip.id,
        "member_id": member.id,
        "bank_bin": "970436",
        "account_number_encrypted": b"\x01" + b"\x00" * 40,
        "account_last4": "6789",
        "account_name": "NGUYEN VAN AN",
    }
    return BankAccount(**(fields | overrides))


def make_event(
    trip: Trip,
    kind: EventKind | str = "member_added",
    actor: Member | None = None,
    subject: Member | None = None,
    **overrides: Any,
) -> TripEvent:
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "trip_id": trip.id,
        "kind": kind,
        "actor_member_id": actor.id if actor else None,
        "subject_member_id": subject.id if subject else None,
    }
    return TripEvent(**(fields | overrides))


def make_device(**overrides: Any) -> Device:
    now = datetime.now(UTC)
    token_hash = hashlib.sha256(secrets.token_bytes(32)).digest()
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "token_hash": token_hash,
        "last_seen_at": now,
        "expires_at": now + timedelta(days=1),
    }
    return Device(**(fields | overrides))


def make_membership(device: Device, member: Member, **overrides: Any) -> Membership:
    fields: dict[str, Any] = {
        "device_id": device.id,
        "trip_id": member.trip_id,
        "member_id": member.id,
    }
    return Membership(**(fields | overrides))


def make_idempotency_key(device: Device, **overrides: Any) -> IdempotencyKey:
    fields: dict[str, Any] = {
        "device_id": device.id,
        "key": uuid.uuid4(),
        "route": "POST /trips/{trip_id}/expenses",
        "request_hash": b"\x00" * 32,
        "status_code": None,
        "response_body": None,
    }
    return IdempotencyKey(**(fields | overrides))


async def add_trip(session: AsyncSession, member_count: int = 2) -> tuple[Trip, list[Member]]:
    trip = make_trip()
    session.add(trip)
    await session.flush()
    members = [make_member(trip, position) for position in range(member_count)]
    session.add_all(members)
    await session.flush()
    return trip, members


async def check_deferred_constraints(session: AsyncSession) -> None:
    """Run the member FK checks that would otherwise wait for a commit these tests never make."""
    await session.flush()
    await session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


async def assert_rejected(session: AsyncSession, constraint: str, *rows: Base) -> None:
    """Write ``rows`` in a savepoint and assert the database rejects them with ``constraint``."""
    with pytest.raises(IntegrityError, match=constraint):
        async with session.begin_nested():
            session.add_all(rows)
            await check_deferred_constraints(session)
