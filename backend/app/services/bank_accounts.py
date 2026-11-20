"""Encrypted member bank account management and static bank registry helpers."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.domain.banks import BANKS, find_bank
from app.repositories import bank_accounts as repository
from app.repositories import events
from app.repositories.models import BankAccount
from app.services.trip_guards import lock_trip_for_actor, require_unlocked_trip


@dataclass(frozen=True)
class BankView:
    """Static Vietnamese bank reference metadata exposed to the API layer."""

    bin: str
    code: str
    short_name: str


@dataclass(frozen=True)
class NewBankAccount:
    """Validated plaintext bank account inputs pending AES-GCM encryption."""

    bank_bin: str
    account_number: str = field(repr=False)
    account_name: str


@dataclass(frozen=True)
class BankAccountView:
    """Masked bank account summary safe for trip-wide display and event metadata."""

    member_id: uuid.UUID
    bank_bin: str
    bank_short_name: str
    account_last4: str
    account_name: str
    updated_at: datetime
    bank_account_changed_at: datetime | None


def list_banks() -> tuple[BankView, ...]:
    """Return all supported NAPAS 247 banks in curated reference order."""
    return tuple(BankView(bank.bin, bank.code, bank.short_name) for bank in BANKS)


def is_known_bank(bank_bin: str) -> bool:
    """Return whether ``bank_bin`` matches a supported VietQR bank BIN."""
    return find_bank(bank_bin) is not None


def bank_account_aad(trip_id: uuid.UUID, member_id: uuid.UUID) -> bytes:
    """Bind ciphertext to ``(trip_id, member_id)`` so row swaps fail AEAD verification."""
    return f"bank:v1:{trip_id}:{member_id}".encode()


def bank_short_name(bank_bin: str) -> str:
    """Resolve display short name for ``bank_bin``, falling back to raw BIN."""
    bank = find_bank(bank_bin)
    return bank_bin if bank is None else bank.short_name


def _view(account: BankAccount, changed_at: datetime | None) -> BankAccountView:
    return BankAccountView(
        member_id=account.member_id,
        bank_bin=account.bank_bin,
        bank_short_name=bank_short_name(account.bank_bin),
        account_last4=account.account_last4,
        account_name=account.account_name,
        updated_at=account.updated_at,
        bank_account_changed_at=changed_at,
    )


async def _lock_for_own_write(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> bool:
    """Acquire shared trip lock on an unlocked trip after post-lock active-caller verification."""
    trip = await lock_trip_for_actor(
        session, trip_id, member_id, require_open=False, exclusive=False
    )
    if trip is None:
        return False
    require_unlocked_trip(trip)
    return True


async def set_own_bank_account(
    session: AsyncSession,
    key: bytes,
    trip_id: uuid.UUID,
    member_id: uuid.UUID,
    data: NewBankAccount,
    now: datetime,
) -> BankAccountView | None:
    """Encrypt and upsert the caller's bank account and append an audit event."""
    if not await _lock_for_own_write(session, trip_id, member_id):
        return None
    account = BankAccount(
        trip_id=trip_id,
        member_id=member_id,
        bank_bin=data.bank_bin,
        account_number_encrypted=encrypt(
            key, data.account_number, bank_account_aad(trip_id, member_id)
        ),
        account_last4=data.account_number[-4:],
        account_name=data.account_name,
        updated_at=now,
    )
    await repository.upsert_bank_account(session, account, now)
    events.add_event(session, trip_id, "bank_account_set", member_id, member_id, now)
    return _view(account, now)


async def delete_own_bank_account(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID, now: datetime
) -> bool:
    """Delete the caller's bank account idempotently and record removal if deleted."""
    if not await _lock_for_own_write(session, trip_id, member_id):
        return False
    if await repository.delete_bank_account(session, trip_id, member_id):
        events.add_event(session, trip_id, "bank_account_removed", member_id, member_id, now)
    return True


async def list_bank_accounts(session: AsyncSession, trip_id: uuid.UUID) -> list[BankAccountView]:
    """List masked trip bank accounts ordered by member position with change timestamps."""
    changes = await events.latest_bank_account_changes(session, trip_id)
    accounts = await repository.list_bank_accounts(session, trip_id)
    return [_view(a, changes.get(a.member_id)) for a in accounts]
