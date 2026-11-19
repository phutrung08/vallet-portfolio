import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, get_now
from app.api.errors import register_error_handlers
from app.api.security_headers import SecurityHeadersMiddleware
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.logging import configure_logging
from app.repositories.models import Device
from app.services.errors import RuleViolation
from tests.api.test_csrf import CSRF_HEADERS

pytestmark = pytest.mark.anyio


class ValidationPayload(BaseModel):
    name: str = Field(max_length=5)
    count: int


@pytest.fixture
def error_app(session: AsyncSession) -> FastAPI:
    configure_logging()
    settings = Settings(_env_file=None, environment="development", cookie_secure=True)
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.cookie_secure)
    register_error_handlers(app, hsts=settings.cookie_secure)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_now] = lambda: datetime.now(UTC)

    @app.post("/_test/validate")
    def validate(payload: ValidationPayload) -> dict[str, str]:
        return {"name": payload.name}

    @app.get("/_test/trips/{trip_id}")
    def trip(trip_id: UUID) -> dict[str, str]:
        return {"trip_id": str(trip_id)}

    @app.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/_test/rule/{code}")
    def rule(code: str, difference: int | None = None) -> None:
        if code == "member_already_joined":
            raise RuleViolation("member_already_joined")
        if code == "device_trip_limit_reached":
            raise RuleViolation("device_trip_limit_reached")
        raise RuleViolation("invalid_split", difference=difference)

    return app


@pytest.fixture
async def client(error_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="https://test", headers=CSRF_HEADERS
    ) as client:
        yield client


async def test_validation_error_lists_fields_without_echoing_input(client: AsyncClient) -> None:
    response = await client.post("/_test/validate", json={"name": "SECRET-VALUE", "count": "x"})

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Invalid request",
        "fields": ["body.count", "body.name"],
    }
    assert "SECRET-VALUE" not in response.text


async def test_malformed_trip_id_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.get("/_test/trips/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["fields"] == ["path.trip_id"]


async def test_unknown_route_uses_the_error_shape(client: AsyncClient) -> None:
    response = await client.get("/no-such-route")

    assert (response.status_code, response.json()) == (
        404,
        {"code": "not_found", "message": "Not Found"},
    )


async def test_rule_violations_map_to_documented_status_and_extra_fields(
    client: AsyncClient,
) -> None:
    joined = await client.get("/_test/rule/member_already_joined")
    capped = await client.get("/_test/rule/device_trip_limit_reached")
    split = await client.get("/_test/rule/invalid_split?difference=-500")

    assert (joined.status_code, joined.json()["code"]) == (409, "member_already_joined")
    assert (capped.status_code, capped.json()["code"]) == (409, "device_trip_limit_reached")
    assert (split.status_code, split.json()) == (
        422,
        {"code": "invalid_split", "message": "Split does not add up", "difference": -500},
    )


async def test_unexpected_exception_is_a_generic_500_with_redacted_logs(
    error_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    transport = ASGITransport(app=error_app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="https://test", headers=CSRF_HEADERS
    ) as client:
        response = await client.get("/_test/boom", headers={"Cookie": "vl_device=SECRETCOOKIE"})

    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "message": "Internal server error"}
    assert "secret internal detail" not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    logged = [r for r in caplog.records if r.name == "app.api.errors"]
    assert [r.levelno for r in logged] == [logging.ERROR]
    assert "SECRETCOOKIE" not in caplog.text


async def test_integrity_error_at_commit_is_a_409(
    session: AsyncSession,
) -> None:
    settings = Settings(_env_file=None, environment="development", cookie_secure=True)
    app = FastAPI()
    register_error_handlers(app, hsts=True)
    app.dependency_overrides[get_session] = lambda: session

    @app.post("/_test/conflict")
    async def conflict(db: DbSession) -> None:
        existing = await session.scalar(select(Device.token_hash).limit(1))
        duplicate = existing or (b"\x02" * 32)
        if existing is None:
            session.add(Device(token_hash=duplicate, expires_at=datetime.now(UTC) + timedelta(1)))
            await session.flush()
        # Add without flush so IntegrityError fires inside get_db()'s commit.
        db.add(Device(token_hash=duplicate, expires_at=datetime.now(UTC) + timedelta(1)))

    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await client.post("/_test/conflict")

    assert response.status_code == 409
    assert response.json() == {"code": "conflict", "message": "Conflict"}
    assert "uq_devices" not in response.text
