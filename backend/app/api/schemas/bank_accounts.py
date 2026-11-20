"""Pydantic schemas for bank registry and encrypted member bank account endpoints."""

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.services.bank_accounts import NewBankAccount, is_known_bank
from app.services.names import normalise_account_name

_ACCOUNT_NUMBER = re.compile(r"[0-9]{6,19}")


def _known_bin(value: str) -> str:
    if not is_known_bank(value):
        raise ValueError("unknown bank")
    return value


def _account_number(value: str) -> str:
    # Error message omits the input so account numbers cannot appear in validation telemetry.
    digits = value.replace(" ", "")
    if _ACCOUNT_NUMBER.fullmatch(digits) is None:
        raise ValueError("must be 6 to 19 digits")
    return digits


BankBin = Annotated[str, Field(max_length=6), AfterValidator(_known_bin)]
AccountNumber = Annotated[str, Field(max_length=40, repr=False), AfterValidator(_account_number)]
AccountName = Annotated[str, Field(max_length=200), AfterValidator(normalise_account_name)]


class BankAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank_bin: BankBin
    account_number: AccountNumber
    account_name: AccountName

    def to_new_account(self) -> NewBankAccount:
        return NewBankAccount(self.bank_bin, self.account_number, self.account_name)


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: UUID
    bank_bin: str
    bank_short_name: str
    account_last4: str
    account_name: str
    updated_at: datetime
    bank_account_changed_at: datetime | None


class BankAccountListOut(BaseModel):
    accounts: list[BankAccountOut]


class BankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bin: str
    code: str
    short_name: str


class BankListOut(BaseModel):
    banks: list[BankOut]
