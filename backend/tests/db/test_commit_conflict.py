"""A deferred member FK failing at real COMMIT becomes a 409 (outside the rollback fixture)."""

import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.main import create_app
from app.repositories import trips as trip_repository
from app.repositories.models import Device, Member, Membership, Payment, Trip
from app.services.devices import create_device
from tests.db.factories import make_member, make_membership, make_trip

pytestmark = pytest.mark.anyio

CSRF_HEADERS = {"X-Requested-With": "vallet"}


@dataclass(frozen=True)
class Committed:
    trip: Trip
    members: list[Member]
    outsider: Member
    raw_token: str


@pytest.fixture
async def committed(db_engine: AsyncEngine) -> AsyncIterator[Committed]:
    trip, other = make_trip(), make_trip()
    members = [make_member(trip, 0), make_member(trip, 1)]
    outsider = make_member(other, 0)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        session.add_all([trip, other])
        await session.flush()
        session.add_all([*members, outsider])
        created = create_device(session, datetime.now(UTC), timedelta(days=1))
        await session.flush()
        session.add(make_membership(Device(id=created.device_id), members[0]))
        await session.commit()
    try:
        yield Committed(trip, members, outsider, created.raw_token)
    finally:
        async with AsyncSession(db_engine) as cleanup:
            await cleanup.execute(
                delete(Membership).where(Membership.device_id == created.device_id)
            )
            await cleanup.execute(delete(Trip).where(Trip.id.in_([trip.id, other.id])))
            await cleanup.execute(delete(Device).where(Device.id == created.device_id))
            await cleanup.commit()


@pytest.fixture
async def client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    dev_settings = Settings(_env_file=None, environment="development", cookie_secure=True)
    app: FastAPI = create_app(dev_settings)

    async def committing_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = committing_session
    app.dependency_overrides[get_settings] = lambda: dev_settings
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="https://test", headers=CSRF_HEADERS
        ) as async_client,
    ):
        yield async_client


async def test_a_member_of_another_trip_failing_at_commit_is_a_409(
    client: AsyncClient,
    committed: Committed,
    db_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_members = trip_repository.list_members

    async def members_with_outsider(session: AsyncSession, trip_id: uuid.UUID) -> Sequence[Member]:
        # Let the foreign member past the service membership check so deferred FK enforces it.
        return [*await list_members(session, trip_id), committed.outsider]

    monkeypatch.setattr(trip_repository, "list_members", members_with_outsider)
    client.cookies.set("__Host-vl_device", committed.raw_token)
    payer = committed.members[0]

    response = await client.post(
        f"/trips/{committed.trip.id}/payments",
        json={
            "payer": str(payer.id),
            "payee": str(committed.outsider.id),
            "amount": 100_000,
            "paid_on": "2026-11-08",
        },
    )

    assert response.status_code == 409, response.text
    assert response.json() == {"code": "conflict", "message": "Conflict"}
    async with AsyncSession(db_engine) as reader:
        count = select(func.count()).where(Payment.trip_id == committed.trip.id)
        assert await reader.scalar(count) == 0
