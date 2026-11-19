from datetime import date
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas.names import MemberName

# Real tokens have 43 characters; anything far longer is refused before any work.
ShareToken = Annotated[str, Field(max_length=64, repr=False)]


class JoinPreviewRequest(BaseModel):
    """Request body carrying a share token to preview."""

    model_config = ConfigDict(extra="forbid")

    token: ShareToken


class JoinRequest(BaseModel):
    """Request body to claim an existing unjoined member or create a new one."""

    model_config = ConfigDict(extra="forbid")

    token: ShareToken
    member_id: UUID | None = None
    new_name: MemberName | None = None

    @model_validator(mode="after")
    def _exactly_one_choice(self) -> Self:
        if (self.member_id is None) == (self.new_name is None):
            raise ValueError("give exactly one of member_id and new_name")
        return self

    @property
    def choice(self) -> UUID | str:
        """Return the validated member UUID or new display name."""
        if self.member_id is not None:
            return self.member_id
        if self.new_name is not None:
            return self.new_name
        raise ValueError("validated to hold exactly one of member_id and new_name")


class PreviewTripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    starts_on: date | None
    ends_on: date | None
    locked: bool
    closed: bool


class PreviewMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    joined: bool


class JoinPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip: PreviewTripOut
    members: list[PreviewMemberOut]
    me: UUID | None
