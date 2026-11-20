"""Tests for StripPrefixMiddleware and create_app(strip_prefix=...)."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.types import Receive, Scope, Send

from app.api.prefix import StripPrefixMiddleware
from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.anyio


def _dev_settings() -> Settings:
    return Settings(_env_file=None, environment="development", cookie_secure=True)


async def test_strip_prefix_serves_api_health_and_404_with_security_headers() -> None:
    application = create_app(_dev_settings(), strip_prefix="/api")
    transport = ASGITransport(app=application, client=("198.51.100.1", 50_000))
    async with AsyncClient(transport=transport, base_url="https://vallet.example.com") as client:
        ok = await client.get("/api/health")
        bare = await client.get("/api")
        unprefixed = await client.get("/health")

    assert ok.status_code == 200
    assert ok.json() == {"status": "ok"}
    assert ok.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"

    assert bare.status_code == 404
    assert bare.json() == {"code": "not_found", "message": "Not Found"}
    assert bare.headers["x-content-type-options"] == "nosniff"

    assert unprefixed.status_code == 200
    assert unprefixed.json() == {"status": "ok"}


async def test_strip_prefix_enforces_csrf_and_trip_create_rate_limit() -> None:
    application = create_app(_dev_settings(), strip_prefix="/api")
    transport = ASGITransport(app=application, client=("198.51.100.2", 50_000))
    async with AsyncClient(transport=transport, base_url="https://vallet.example.com") as client:
        for _ in range(10):
            blocked_csrf = await client.post("/api/trips", json={})
            assert blocked_csrf.status_code == 403
            assert blocked_csrf.json()["code"] == "csrf_rejected"

        throttled = await client.post("/api/trips", json={})

    assert throttled.status_code == 429
    assert throttled.json()["code"] == "rate_limited"
    assert (
        throttled.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )


async def test_strip_prefix_middleware_updates_raw_path_and_skips_lifespan() -> None:
    seen: list[Scope] = []

    async def capture(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope)

    middleware = StripPrefixMiddleware(capture, prefix="/api/")

    async def noop_receive() -> dict[str, object]:
        return {}

    async def noop_send(message: dict[str, object]) -> None:
        return None

    await middleware({"type": "lifespan"}, noop_receive, noop_send)
    await middleware(
        {"type": "http", "path": "/api/trips/abc def", "raw_path": b"/api/trips/abc%20def"},
        noop_receive,
        noop_send,
    )
    await middleware({"type": "http", "path": "/api", "raw_path": b"/api"}, noop_receive, noop_send)

    assert seen[0] == {"type": "lifespan"}
    assert seen[1]["path"] == "/trips/abc def"
    assert seen[1]["raw_path"] == b"/trips/abc%20def"
    assert seen[1]["root_path"] == "/api"
    assert seen[2]["path"] == "/"
    assert seen[2]["raw_path"] == b"/"
