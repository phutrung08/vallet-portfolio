"""Pydantic response schema for VietQR settlement payload endpoint."""

from pydantic import BaseModel, ConfigDict


class VietQrOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payload: str
    bank_bin: str
    bank_short_name: str
    account_name: str
    account_last4: str
    amount: int
    message: str
