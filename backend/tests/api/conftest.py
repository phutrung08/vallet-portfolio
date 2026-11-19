"""An app from create_app() plus test-only probe routes, bound to the rolled-back test session."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    DbSession,
    MemberContext,
    OptionalDeviceId,
    ReadonlyDeviceId,
    ensure_device,
    get_now,
    require_member,
)
from app.api.idempotency import IdempotentCreate
from app.core.config import Settings, get_settings
from app.core.db import get_readonly_session, get_session
from app.main import create_app
from app.repositories import events as event_repository
from app.repositories.models import Device
from app.services.errors import RuleViolation

# What the frontend client sends on every write; the CSRF middleware rejects writes without it.
CSRF_HEADERS = {"X-Requested-With": "vallet"}

probe = APIRouter(prefix="/_test")


@probe.post("/device")
def ensure(device_id: Annotated[uuid.UUID, Depends(ensure_device)]) -> dict[str, str]:
    return {"device_id": str(device_id)}


@probe.get("/me")
def me(device_id: OptionalDeviceId) -> dict[str, str | None]:
    return {"device_id": str(device_id) if device_id else None}


@probe.get("/me-readonly")
def me_readonly(device_id: ReadonlyDeviceId) -> dict[str, str | None]:
    return {"device_id": str(device_id) if device_id else None}


@probe.get("/trips/{trip_id}")
def trip(member: Annotated[MemberContext, Depends(require_member)]) -> dict[str, str]:
    return {"member_id": str(member.member_id), "device_id": str(member.device_id)}


class Payload(BaseModel):
    name: str = Field(max_length=5)
    count: int


@probe.post("/validate")
def validate(payload: Payload) -> dict[str, str]:
    return {"name": payload.name}


@probe.get("/boom")
def boom() -> None:
    raise RuntimeError("secret internal detail")


@probe.post("/conflict")
def conflict(session: DbSession, device_id: OptionalDeviceId) -> None:
    assert device_id is not None
    # Two rows with the same token_hash hit the unique constraint only when get_db() commits.
    duplicate_hash = device_id.bytes + b"\x00" * 16
    expires = datetime.now(UTC) + timedelta(days=1)
    session.add(Device(token_hash=duplicate_hash, expires_at=expires))
    session.add(Device(token_hash=duplicate_hash, expires_at=expires))


class IdempotentBody(BaseModel):
    amount: int = Field(gt=0)
    fail_rule: bool = False


class IdempotentOut(BaseModel):
    record_id: uuid.UUID
    created_by: uuid.UUID
    amount: int


@probe.post("/trips/{trip_id}/idempotent-a", status_code=201)
async def idempotent_a(
    body: IdempotentBody, writer: IdempotentCreate, now: Annotated[datetime, Depends(get_now)]
) -> IdempotentOut:
    async def _write() -> IdempotentOut:
        if body.fail_rule:
            raise RuleViolation("trip_locked")
        event_repository.add_event(
            writer.session,
            writer.caller.trip_id,
            "member_added",
            writer.caller.member_id,
            writer.caller.member_id,
            now,
        )
        return IdempotentOut(
            record_id=uuid.uuid4(),
            created_by=writer.caller.member_id,
            amount=body.amount,
        )

    return await writer.run(body, IdempotentOut, _write)


@probe.post("/trips/{trip_id}/idempotent-b", status_code=201)
async def idempotent_b(
    body: IdempotentBody, writer: IdempotentCreate, now: Annotated[datetime, Depends(get_now)]
) -> IdempotentOut:
    async def _write() -> IdempotentOut:
        event_repository.add_event(
            writer.session,
            writer.caller.trip_id,
            "member_renamed",
            writer.caller.member_id,
            writer.caller.member_id,
            now,
        )
        return IdempotentOut(
            record_id=uuid.uuid4(),
            created_by=writer.caller.member_id,
            amount=body.amount,
        )

    return await writer.run(body, IdempotentOut, _write)


@dataclass
class FrozenClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None, environment="development", cookie_secure=True, device_ttl_days=180
    )


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime.now(UTC))


@pytest.fixture
def app(session: AsyncSession, settings: Settings, clock: FrozenClock) -> FastAPI:
    app = create_app(settings)
    app.include_router(probe)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_readonly_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_now] = clock
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # https so the client's cookie jar keeps sending the Secure cookie back.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test", headers=CSRF_HEADERS
    ) as client:
        yield client


@pytest.fixture
async def other_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A second browser: same app and database, its own cookie jar."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test", headers=CSRF_HEADERS
    ) as other:
        yield other
