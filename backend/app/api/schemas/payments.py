"""Pydantic schemas for settlement payment endpoints."""

from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.api.schemas.expenses import Amount
from app.api.schemas.names import PaymentNote
from app.services.payments import NewPayment


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payer: UUID
    payee: UUID
    amount: Amount
    paid_on: date
    note: PaymentNote = None

    @model_validator(mode="after")
    def _payer_is_not_payee(self) -> Self:
        if self.payer == self.payee:
            raise ValueError("payer and payee must differ")
        return self

    def to_new_payment(self) -> NewPayment:
        return NewPayment(self.payer, self.payee, self.amount, self.paid_on, self.note)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payer: UUID
    payee: UUID
    amount: int
    paid_on: date
    note: str | None
    created_by: UUID
    created_at: datetime


class PaymentListOut(BaseModel):
    payments: list[PaymentOut]
