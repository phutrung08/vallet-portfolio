"""Pydantic response schemas for trip activity log endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    actor_id: UUID | None
    subject_id: UUID | None
    created_at: datetime


class EventListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    events: list[EventOut]
    next_before: UUID | None
