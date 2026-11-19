from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from app.core import limits
from app.core.config import Settings
from app.main import create_app
from tests.api.conftest import CSRF_HEADERS

pytestmark = pytest.mark.anyio

EXPECTED = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "cross-origin-resource-policy": "same-site",
}
HSTS = "max-age=31536000; includeSubDomains"

type MakeClient = Callable[[bool], AsyncClient]


def build_app(cookie_secure: bool) -> FastAPI:
    settings = Settings(_env_file=None, environment="development", cookie_secure=cookie_secure)
    app = create_app(settings)

    @app.post("/probe")
    def probe() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/_test/cached")
    def cached(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "private, max-age=60"
        return {"status": "ok"}

    @app.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
async def api() -> AsyncIterator[MakeClient]:
    clients: list[AsyncClient] = []

    def make(cookie_secure: bool) -> AsyncClient:
        transport = ASGITransport(app=build_app(cookie_secure), raise_app_exceptions=False)
        client = AsyncClient(transport=transport, base_url="https://test")
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()


def security_headers(response: httpx.Response) -> dict[str, str]:
    return {name: response.headers[name] for name in EXPECTED if name in response.headers}


async def test_every_response_carries_the_headers_and_hsts_when_secure(api: MakeClient) -> None:
    client = api(True)

    ok = await client.get("/health")
    missing = await client.get("/nowhere")

    for response in (ok, missing):
        assert security_headers(response) == EXPECTED
        assert response.headers["strict-transport-security"] == HSTS


async def test_no_hsts_when_cookies_are_not_secure(api: MakeClient) -> None:
    response = await api(False).get("/health")

    assert security_headers(response) == EXPECTED
    assert "strict-transport-security" not in response.headers


async def test_a_route_cache_control_is_kept(api: MakeClient) -> None:
    response = await api(True).get("/_test/cached")

    assert response.headers["cache-control"] == "private, max-age=60"
    assert security_headers(response) == EXPECTED


async def test_a_csrf_refusal_carries_the_headers(api: MakeClient) -> None:
    response = await api(True).post("/probe", json={})

    assert response.json()["code"] == "csrf_rejected"
    assert security_headers(response) == EXPECTED
    assert response.headers["strict-transport-security"] == HSTS


async def test_a_rate_limit_refusal_carries_the_headers(
    api: MakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "RATE_LIMIT_ALL", 1)
    client = api(True)

    await client.get("/health")
    refused = await client.post("/probe", json={}, headers=CSRF_HEADERS)

    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "60"
    assert security_headers(refused) == EXPECTED
    assert refused.headers["strict-transport-security"] == HSTS


async def test_a_body_limit_refusal_carries_the_headers(api: MakeClient) -> None:
    oversized = b"x" * (limits.MAX_REQUEST_BODY_BYTES + 1)

    response = await api(True).post("/probe", content=oversized, headers=CSRF_HEADERS)

    assert response.status_code == 413
    assert security_headers(response) == EXPECTED


async def test_an_unhandled_500_still_carries_security_headers_and_hsts(
    api: MakeClient,
) -> None:
    secure_500 = await api(True).get("/_test/boom")
    plain_500 = await api(False).get("/_test/boom")

    assert secure_500.status_code == 500
    assert security_headers(secure_500) == EXPECTED
    assert secure_500.headers["strict-transport-security"] == HSTS

    assert plain_500.status_code == 500
    assert security_headers(plain_500) == EXPECTED
    assert "strict-transport-security" not in plain_500.headers
