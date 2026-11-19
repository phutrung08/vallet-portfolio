import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_token
from app.repositories.models import Device, Member, Membership
from tests.api.test_device_session import new_device_token
from tests.db.factories import add_trip, make_membership

pytestmark = pytest.mark.anyio

NOT_FOUND = {"code": "not_found", "message": "Not Found"}


async def attach_member(
    client: AsyncClient, settings: Settings, session: AsyncSession, member: Member
) -> tuple[str, Membership]:
    """Attach a device cookie in the client's jar to ``member`` and commit the savepoint."""
    token = await new_device_token(client, settings)
    device = await session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    assert device is not None
    membership = make_membership(device, member)
    session.add(membership)
    await session.commit()
    return token, membership


async def test_member_gets_their_member_id(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    trip, (_, binh) = await add_trip(session)
    trip_id, binh_id = trip.id, binh.id
    await attach_member(client, settings, session, binh)

    response = await client.get(f"/_test/trips/{trip_id}")

    assert response.status_code == 200
    assert response.json()["member_id"] == str(binh_id)


async def test_other_trip_and_missing_trip_look_the_same(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    _, (an, _) = await add_trip(session)
    other, _ = await add_trip(session)
    other_id = other.id
    await attach_member(client, settings, session, an)

    not_member = await client.get(f"/trips/{other_id}")
    missing = await client.get(f"/trips/{uuid.uuid4()}")

    assert not_member.status_code == missing.status_code == 404
    assert not_member.json() == missing.json() == NOT_FOUND
    assert not_member.content == missing.content


async def test_revoked_membership_is_not_found(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id = trip.id
    _, membership = await attach_member(client, settings, session, an)
    membership.revoked_at = datetime.now(UTC)
    await session.commit()

    response = await client.get(f"/trips/{trip_id}")

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


async def test_removed_member_is_not_found(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id = trip.id
    await attach_member(client, settings, session, an)
    an.removed_at = datetime.now(UTC)
    await session.commit()

    response = await client.get(f"/trips/{trip_id}")

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


async def test_no_session_is_not_found_rather_than_unauthenticated(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip, _ = await add_trip(session)
    trip_id = trip.id
    await session.commit()

    response = await client.get(f"/trips/{trip_id}")

    assert (response.status_code, response.json()) == (404, NOT_FOUND)
