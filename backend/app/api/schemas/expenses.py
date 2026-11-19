"""Pydantic request and response schemas for trip expense endpoints."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidatorFunctionWrapHandler,
    WrapValidator,
)

from app.api.schemas.names import ExpenseNote, ExpensePlace, ExpenseTitle
from app.core.limits import MAX_ACTIVE_MEMBERS
from app.services.expenses import EXPENSE_CATEGORIES, NewExpense

MAX_AMOUNT = 10**12
# Strict int bounds reject JSON booleans and floats masquerading as minor units or weights.
Amount = Annotated[int, Field(strict=True, ge=1, le=MAX_AMOUNT)]
ShareCount = Annotated[int, Field(strict=True, ge=0, le=10_000)]
BasisPoints = Annotated[int, Field(strict=True, ge=0, le=10_000)]  # 10_000 = 100%
ExactAmount = Annotated[int, Field(strict=True, ge=0, le=MAX_AMOUNT)]


def _known_category(value: str) -> str:
    if value not in EXPENSE_CATEGORIES:
        raise ValueError("unknown category")
    return value


def _unique_ids(ids: list[UUID]) -> list[UUID]:
    if len(set(ids)) != len(ids):
        raise ValueError("participants must be unique")
    return ids


def _no_merged_keys(value: object, handler: ValidatorFunctionWrapHandler) -> object:
    # Distinct UUID casings ("AB.." and "ab..") would collide when coerced to dict[UUID, W].
    parsed = handler(value)
    if isinstance(value, dict) and isinstance(parsed, dict) and len(parsed) != len(value):
        raise ValueError("member ids must be unique")
    return parsed


Category = Annotated[str, AfterValidator(_known_category)]
_SIZE = Field(min_length=1, max_length=MAX_ACTIVE_MEMBERS)
type _Weights[W] = Annotated[dict[UUID, W], _SIZE, WrapValidator(_no_merged_keys)]


class EqualSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["equal"]
    participants: Annotated[list[UUID], _SIZE, AfterValidator(_unique_ids)]

    def weights(self) -> dict[UUID, int]:
        return dict.fromkeys(self.participants, 1)


class SharesSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["shares"]
    shares: _Weights[ShareCount]

    def weights(self) -> dict[UUID, int]:
        return self.shares


class PercentSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["percent"]
    basis_points: _Weights[BasisPoints]

    def weights(self) -> dict[UUID, int]:
        return self.basis_points


class ExactSplit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["exact"]
    amounts: _Weights[ExactAmount]

    def weights(self) -> dict[UUID, int]:
        return self.amounts


Split = Annotated[EqualSplit | SharesSplit | PercentSplit | ExactSplit, Field(discriminator="mode")]


class CreateExpenseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ExpenseTitle
    amount: Amount
    category: Category
    spent_on: date
    # Required even when null: an omitted payer must not silently charge the shared fund.
    paid_by: UUID | None
    split: Split
    note: ExpenseNote = None
    place: ExpensePlace = None

    def to_new_expense(self) -> NewExpense:
        return NewExpense(
            title=self.title,
            amount=self.amount,
            category=self.category,
            spent_on=self.spent_on,
            paid_by=self.paid_by,
            split_mode=self.split.mode,
            weights=self.split.weights(),
            note=self.note,
            place=self.place,
        )


class EditExpenseRequest(CreateExpenseRequest):
    # Optimistic concurrency version expected by the client.
    version: Annotated[int, Field(strict=True, ge=1)]


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: UUID
    weight: int
    amount: int


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    amount: int
    category: str
    spent_on: date
    paid_by: UUID | None
    split_mode: str
    shares: list[ShareOut]
    note: str | None
    place: str | None
    created_by: UUID
    updated_by: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class ExpenseListOut(BaseModel):
    expenses: list[ExpenseOut]


class DaySummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    count: int
    total: int


class DaysOut(BaseModel):
    days: list[DaySummaryOut]
