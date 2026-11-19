import uuid
from datetime import timedelta
from http.cookies import SimpleCookie

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.models import Device, Membership
from tests.api.conftest import FrozenClock
from tests.api.test_trips import create

pytestmark = pytest.mark.anyio


def cleared_cookie(response: Response, settings: Settings) -> dict[str, str | bool]:
    cookie = SimpleCookie(response.headers["set-cookie"])[settings.device_cookie_name]
    return {key: cookie[key] for key in ("max-age", "path", "samesite", "secure", "httponly")}


async def test_sign_out_revokes_the_device_and_clears_the_cookie(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    detail = await create(client)
    trip_id = detail["id"]
    token = client.cookies[settings.device_cookie_name]
    assert (await client.get(f"/trips/{trip_id}")).status_code == 200

    response = await client.post("/devices/me/sign-out")

    assert response.status_code == 204
    assert cleared_cookie(response, settings) == {
        "max-age": "0",
        "path": "/",
        "samesite": "lax",
        "secure": True,
        "httponly": True,
    }
    membership = await session.scalar(
        select(Membership).where(Membership.trip_id == uuid.UUID(trip_id))
    )
    assert membership is not None
    device = await session.scalar(select(Device).where(Device.id == membership.device_id))
    assert device is not None and device.revoked_at is not None
    # The old token no longer works, even if a client keeps sending it.
    client.cookies.set(settings.device_cookie_name, token)
    assert (await client.get(f"/trips/{trip_id}")).status_code == 404


async def test_sign_out_after_idle_hour_emits_only_one_set_cookie_header(
    client: AsyncClient, settings: Settings, clock: FrozenClock
) -> None:
    await create(client)
    clock.advance(timedelta(hours=2))

    response = await client.post("/devices/me/sign-out")

    assert response.status_code == 204
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 1
    assert cleared_cookie(response, settings)["max-age"] == "0"


async def test_sign_out_keeps_the_member_and_the_membership_row(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)

    await client.post("/devices/me/sign-out")

    rows = await session.scalars(
        select(Membership).where(Membership.member_id == uuid.UUID(detail["me"]))
    )
    assert [row.revoked_at for row in rows] == [None]


async def test_sign_out_without_a_cookie_is_204(client: AsyncClient, settings: Settings) -> None:
    response = await client.post("/devices/me/sign-out")

    assert response.status_code == 204
    assert cleared_cookie(response, settings)["max-age"] == "0"


async def test_signing_out_twice_is_204(client: AsyncClient) -> None:
    await client.post("/_test/device")

    first = await client.post("/devices/me/sign-out")
    second = await client.post("/devices/me/sign-out")

    assert (first.status_code, second.status_code) == (204, 204)
