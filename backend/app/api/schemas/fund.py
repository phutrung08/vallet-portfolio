"""Pydantic schemas for shared fund endpoints."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.schemas.expenses import Amount


class ContributionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    amount: Amount
    contributed_on: date


class HolderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Required even when null: an omitted holder must not silently turn the fund off.
    holder_id: UUID | None


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_id: UUID
    amount: int
    contributed_on: date
    created_by: UUID
    created_at: datetime


class MemberContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: UUID
    contributed: int


class FundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    holder_id: UUID | None
    contributed: int
    spent: int
    remaining: int
    members: list[MemberContributionOut]
    contributions: list[ContributionOut]
