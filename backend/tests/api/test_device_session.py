from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import Morsel, SimpleCookie
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    MemberContext,
    OptionalDeviceId,
    ReadonlyDeviceId,
    ensure_device,
    get_now,
    require_member,
)
from app.api.errors import register_error_handlers
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import hash_token, new_token
from app.repositories.models import Device, Membership
from tests.db.factories import add_trip

pytestmark = pytest.mark.anyio

TTL_SECONDS = 180 * 24 * 3600


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
def session_app(session: AsyncSession, settings: Settings, clock: FrozenClock) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app, hsts=settings.cookie_secure)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_now] = clock

    @app.post("/_test/device")
    def ensure(device_id: Annotated[UUID, Depends(ensure_device)]) -> dict[str, str]:
        return {"device_id": str(device_id)}

    @app.get("/_test/me")
    def me(device_id: OptionalDeviceId) -> dict[str, str | None]:
        return {"device_id": str(device_id) if device_id else None}

    @app.get("/_test/me-readonly")
    def me_readonly(device_id: ReadonlyDeviceId) -> dict[str, str | None]:
        return {"device_id": str(device_id) if device_id else None}

    @app.get("/_test/trips/{trip_id}")
    def trip(member: Annotated[MemberContext, Depends(require_member)]) -> dict[str, str]:
        return {"member_id": str(member.member_id), "device_id": str(member.device_id)}

    return app


@pytest.fixture
async def client(session_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=session_app), base_url="https://test"
    ) as client:
        yield client


def device_cookie(response: Response, settings: Settings) -> Morsel[str]:
    cookies = SimpleCookie(response.headers["set-cookie"])
    return cookies[settings.device_cookie_name]


async def new_device_token(client: AsyncClient, settings: Settings) -> str:
    response = await client.post("/_test/device")
    assert response.status_code == 200
    return device_cookie(response, settings).value


async def me(client: AsyncClient, settings: Settings, token: str) -> Response:
    client.cookies.clear()
    return await client.get(
        "/_test/me", headers={"Cookie": f"{settings.device_cookie_name}={token}"}
    )


async def stored_device(session: AsyncSession, token: str) -> Device:
    device = await session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    assert device is not None
    return device


async def test_ensure_device_sets_a_locked_down_cookie(
    client: AsyncClient, settings: Settings
) -> None:
    response = await client.post("/_test/device")

    cookie = device_cookie(response, settings)
    assert cookie.key == "__Host-vl_device"
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == str(TTL_SECONDS)
    assert cookie["domain"] == ""


async def test_insecure_settings_drop_secure_and_the_host_prefix(
    client: AsyncClient, settings: Settings
) -> None:
    settings.cookie_secure = False

    cookie = device_cookie(await client.post("/_test/device"), settings)

    assert cookie.key == "vl_device"
    assert cookie["secure"] == ""
    assert cookie["httponly"] is True


async def test_only_the_token_hash_is_stored(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    token = await new_device_token(client, settings)

    device = await stored_device(session, token)
    row = await session.execute(text("SELECT * FROM devices WHERE id = :id"), {"id": device.id})
    assert token not in repr(row.one())


async def test_existing_device_is_reused_without_a_new_cookie(client: AsyncClient) -> None:
    first = await client.post("/_test/device")

    second = await client.post("/_test/device")

    assert second.json() == first.json()
    assert "set-cookie" not in second.headers


async def test_valid_cookie_is_recognised(client: AsyncClient, settings: Settings) -> None:
    created = await client.post("/_test/device")
    token = device_cookie(created, settings).value

    response = await me(client, settings, token)

    assert response.status_code == 200
    assert response.json() == created.json()


@pytest.mark.parametrize("token", [new_token(), "garbage", "a" * 44, ""])
async def test_unknown_or_malformed_token_resolves_to_none(
    client: AsyncClient, settings: Settings, token: str
) -> None:
    response = await me(client, settings, token)

    assert response.status_code == 200
    assert response.json() == {"device_id": None}


async def test_require_member_returns_uniform_404_when_unauthenticated_or_non_member(
    client: AsyncClient, settings: Settings, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await session.commit()

    no_cookie = await client.get(f"/_test/trips/{trip_id}")
    assert (no_cookie.status_code, no_cookie.json()) == (
        404,
        {"code": "not_found", "message": "Not Found"},
    )

    token = await new_device_token(client, settings)
    not_member = await client.get(f"/_test/trips/{trip_id}")
    assert (not_member.status_code, not_member.json()) == (
        404,
        {"code": "not_found", "message": "Not Found"},
    )

    device = await stored_device(session, token)
    session.add(Membership(device_id=device.id, trip_id=trip_id, member_id=an_id))
    await session.commit()

    ok = await client.get(f"/_test/trips/{trip_id}")
    assert ok.status_code == 200
    assert ok.json()["member_id"] == str(an_id)


async def test_revoked_or_expired_device_is_ignored(
    client: AsyncClient, settings: Settings, session: AsyncSession, clock: FrozenClock
) -> None:
    token = await new_device_token(client, settings)
    device = await stored_device(session, token)
    device.revoked_at = clock.now
    await session.flush()
    assert (await me(client, settings, token)).json() == {"device_id": None}

    fresh = await new_device_token(client, settings)
    clock.advance(timedelta(days=180))
    assert (await me(client, settings, fresh)).json() == {"device_id": None}


async def test_ensure_device_replaces_an_expired_device(
    client: AsyncClient, settings: Settings, clock: FrozenClock
) -> None:
    old = await new_device_token(client, settings)
    clock.advance(timedelta(days=181))

    client.cookies.clear()
    response = await client.post(
        "/_test/device", headers={"Cookie": f"{settings.device_cookie_name}={old}"}
    )

    assert device_cookie(response, settings).value != old


async def test_activity_slides_expiry_at_most_once_per_hour_and_readonly_never_slides(
    client: AsyncClient, settings: Settings, session: AsyncSession, clock: FrozenClock
) -> None:
    token = await new_device_token(client, settings)
    created_at = clock.now

    clock.advance(timedelta(minutes=59))
    quiet = await me(client, settings, token)
    device = await stored_device(session, token)
    assert "set-cookie" not in quiet.headers
    assert (device.last_seen_at, device.expires_at) == (created_at, created_at + timedelta(180))

    clock.advance(timedelta(minutes=2))
    readonly = await client.get(
        "/_test/me-readonly", headers={"Cookie": f"{settings.device_cookie_name}={token}"}
    )
    await session.refresh(device)
    assert readonly.json() == {"device_id": str(device.id)}
    assert "set-cookie" not in readonly.headers
    assert (device.last_seen_at, device.expires_at) == (created_at, created_at + timedelta(180))

    slid = await me(client, settings, token)
    await session.refresh(device)
    assert device.last_seen_at == clock.now
    assert device.expires_at == clock.now + timedelta(days=180)
    assert device_cookie(slid, settings).value == token
    assert device_cookie(slid, settings)["max-age"] == str(TTL_SECONDS)

    clock.advance(timedelta(minutes=30))
    assert "set-cookie" not in (await me(client, settings, token)).headers
