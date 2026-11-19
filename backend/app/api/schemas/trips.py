from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.api.schemas.names import MemberName, TripName
from app.core.limits import MAX_ACTIVE_MEMBERS
from app.services.names import has_duplicate_names


class CreateTripRequest(BaseModel):
    """Payload to create a new trip and its initial member roster."""

    model_config = ConfigDict(extra="forbid")

    name: TripName
    currency: Literal["VND", "USD"] = "VND"
    starts_on: date | None = None
    ends_on: date | None = None
    uses_fund: Annotated[bool, Field(strict=True)] = False
    creator_name: MemberName
    # Creator + up to MAX_ACTIVE_MEMBERS - 1 additional members.
    member_names: Annotated[list[MemberName], Field(max_length=MAX_ACTIVE_MEMBERS - 1)] = Field(
        default_factory=list
    )

    @field_validator("ends_on")
    @classmethod
    def _ends_on_not_before_start(cls, ends_on: date | None, info: ValidationInfo) -> date | None:
        starts_on = info.data.get("starts_on")
        if ends_on is not None and starts_on is not None and ends_on < starts_on:
            raise ValueError("ends_on must not be before starts_on")
        return ends_on

    @field_validator("member_names")
    @classmethod
    def _names_are_unique(cls, member_names: list[str], info: ValidationInfo) -> list[str]:
        creator_name = info.data.get("creator_name")
        names = member_names if creator_name is None else [creator_name, *member_names]
        if has_duplicate_names(names):
            raise ValueError("member names must be unique ignoring case")
        return member_names


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    position: int
    removed: bool


class TripDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    fund_holder_id: UUID | None
    locked: bool
    closed: bool
    me: UUID
    members: list[MemberOut]


class TripSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    uses_fund: bool
    closed: bool
    member_count: int
    me: UUID


class TripListOut(BaseModel):
    trips: list[TripSummaryOut]


class ShareLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: str
    version: int
