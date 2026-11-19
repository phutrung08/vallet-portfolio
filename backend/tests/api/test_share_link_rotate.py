import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import derive_share_token, hash_token
from app.repositories.models import Trip
from tests.api.test_trip_lock import TRIP_LOCKED
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio


async def rotate(client: AsyncClient, trip_id: str) -> Response:
    return await client.post(f"/trips/{trip_id}/share-link/rotate")


async def stored_link(session: AsyncSession, trip_id: str) -> tuple[int, bytes]:
    statement = (
        select(Trip.share_token_version, Trip.share_token_hash)
        .where(Trip.id == uuid.UUID(trip_id))
        .execution_options(populate_existing=True)
    )
    row = (await session.execute(statement)).one()
    return row[0], row[1]


async def test_rotation_mints_the_next_versions_token_and_stores_its_hash(
    client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail = await create(client)
    old_token = (await client.get(f"/trips/{detail['id']}/share-link")).json()["token"]
    trip_id = detail["id"]

    response = await rotate(client, trip_id)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    link = response.json()
    assert set(link) == {"token", "version"}
    assert link["version"] == 2
    assert link["token"] != old_token
    key = settings.share_link_key_bytes
    assert link["token"] == derive_share_token(key, uuid.UUID(trip_id), 2)
    assert await stored_link(session, trip_id) == (2, hash_token(link["token"]))
    assert (await client.get(f"/trips/{trip_id}/share-link")).json() == link


async def test_each_rotation_bumps_the_version_again(client: AsyncClient) -> None:
    detail = await create(client)

    versions = [(await rotate(client, detail["id"])).json()["version"] for _ in range(3)]

    assert versions == [2, 3, 4]


async def test_a_closed_trip_can_rotate(client: AsyncClient, session: AsyncSession) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/close")

    response = await rotate(client, detail["id"])

    assert (response.status_code, response.json()["version"]) == (200, 2)
    assert (await stored_link(session, detail["id"]))[0] == 2


async def test_a_locked_trip_cannot_rotate_and_its_link_stays(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    before = await stored_link(session, detail["id"])
    await client.post(f"/trips/{detail['id']}/lock")

    response = await rotate(client, detail["id"])

    assert (response.status_code, response.json()) == (403, TRIP_LOCKED)
    assert await stored_link(session, detail["id"]) == before


async def test_outsiders_cannot_rotate(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)

    response = await rotate(other_client, detail["id"])

    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert (await stored_link(session, detail["id"]))[0] == 1
