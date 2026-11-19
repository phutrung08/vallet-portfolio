from pydantic import BaseModel, ConfigDict

from app.api.schemas.names import MemberName


class MemberNameRequest(BaseModel):
    """Request body carrying a normalized member display name."""

    model_config = ConfigDict(extra="forbid")

    display_name: MemberName
