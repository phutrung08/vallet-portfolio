"""Pydantic response schemas for balances and aggregated trip summary endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.schemas.expenses import DaySummaryOut


class FundBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    holder_id: UUID | None
    remaining: int


class MemberStandingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: UUID
    paid: int
    contributed: int
    share: int
    sent: int
    received: int
    net: int
    removed: bool


class TransferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payer: UUID
    payee: UUID
    amount: int


class BalancesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    fund: FundBalanceOut
    members: list[MemberStandingOut]
    transfers: list[TransferOut]


class CategoryBreakdownOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    count: int
    amount: int
    percent: int


class PayerBreakdownOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    paid_by: UUID | None
    count: int
    amount: int


class TripSpendSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    total: int
    expense_count: int
    active_member_count: int
    day_count: int
    per_person: int
    per_day: int
    categories: list[CategoryBreakdownOut]
    payers: list[PayerBreakdownOut]
    days: list[DaySummaryOut]
