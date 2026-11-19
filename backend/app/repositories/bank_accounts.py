import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import BankAccount, Member


async def upsert_bank_account(session: AsyncSession, account: BankAccount, now: datetime) -> None:
    """Insert or replace the member's existing bank account row atomically."""
    values = {
        "trip_id": account.trip_id,
        "member_id": account.member_id,
        "bank_bin": account.bank_bin,
        "account_number_encrypted": account.account_number_encrypted,
        "account_last4": account.account_last4,
        "account_name": account.account_name,
        "created_at": now,
        "updated_at": now,
    }
    replaced = {k: v for k, v in values.items() if k not in {"trip_id", "member_id", "created_at"}}
    statement = (
        insert(BankAccount)
        .values(values)
        .on_conflict_do_update(index_elements=["trip_id", "member_id"], set_=replaced)
    )
    await session.execute(statement)


async def delete_bank_account(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> bool:
    """Return whether an account row was deleted."""
    statement = delete(BankAccount).where(
        BankAccount.trip_id == trip_id, BankAccount.member_id == member_id
    )
    result = cast("CursorResult[object]", await session.execute(statement))
    return result.rowcount > 0


async def find_bank_account(
    session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> BankAccount | None:
    return await session.get(BankAccount, (trip_id, member_id), populate_existing=True)


async def list_bank_accounts(session: AsyncSession, trip_id: uuid.UUID) -> Sequence[BankAccount]:
    """Return the trip's accounts (removed members' too) in member position order."""
    statement = (
        select(BankAccount)
        .join(
            Member,
            (Member.trip_id == BankAccount.trip_id) & (Member.id == BankAccount.member_id),
        )
        .where(BankAccount.trip_id == trip_id)
        .order_by(Member.position)
        .execution_options(populate_existing=True)
    )
    return (await session.scalars(statement)).all()
