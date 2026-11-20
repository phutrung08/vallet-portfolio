import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.csrf import WRITE_METHODS, CsrfMiddleware
from app.core.config import DEV_ORIGIN, Settings
from app.main import create_app
from tests.api.routes import served_routes

pytestmark = pytest.mark.anyio

REJECTED = {"code": "csrf_rejected", "message": "Request rejected"}
CSRF_HEADERS = {"X-Requested-With": "vallet"}


def _build_csrf_app(origins: list[str] | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CsrfMiddleware, allowed_origins=origins or [DEV_ORIGIN])

    @app.api_route("/probe", methods=["GET", "HEAD", "OPTIONS", *WRITE_METHODS], status_code=201)
    def probe() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture
async def bare() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=_build_csrf_app()), base_url="https://test"
    ) as client:
        yield client


@pytest.mark.parametrize("method", sorted(WRITE_METHODS))
async def test_a_write_without_the_header_is_rejected(bare: AsyncClient, method: str) -> None:
    response = await bare.request(method, "/probe", json={})

    assert (response.status_code, response.json()) == (403, REJECTED)


@pytest.mark.parametrize("value", ["", "Vallet", "vallet ", "true", "XMLHttpRequest"])
async def test_a_wrong_header_value_is_rejected(bare: AsyncClient, value: str) -> None:
    response = await bare.post("/probe", json={}, headers={"X-Requested-With": value})

    assert (response.status_code, response.json()) == (403, REJECTED)


async def test_a_repeated_header_is_rejected(bare: AsyncClient) -> None:
    headers = [("X-Requested-With", "vallet"), ("X-Requested-With", "vallet")]

    response = await bare.post("/probe", json={}, headers=headers)

    assert (response.status_code, response.json()) == (403, REJECTED)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "null",
        "",
        "https://localhost:5173",
        "http://localhost:5174",
        "http://localhost",
        "http://localhost:5173/",
        "http://localhost:5173.evil.example",
        "HTTP://LOCALHOST:5173",
    ],
)
async def test_a_foreign_or_malformed_origin_is_rejected(bare: AsyncClient, origin: str) -> None:
    response = await bare.post("/probe", json={}, headers=CSRF_HEADERS | {"Origin": origin})

    assert (response.status_code, response.json()) == (403, REJECTED)


async def test_one_foreign_origin_among_several_is_rejected(bare: AsyncClient) -> None:
    headers = [*CSRF_HEADERS.items(), ("Origin", DEV_ORIGIN), ("Origin", "https://evil.example")]

    response = await bare.post("/probe", json={}, headers=headers)

    assert (response.status_code, response.json()) == (403, REJECTED)


async def test_an_allowed_origin_with_the_header_passes(bare: AsyncClient) -> None:
    response = await bare.post("/probe", json={}, headers=CSRF_HEADERS | {"Origin": DEV_ORIGIN})

    assert response.status_code == 201


async def test_a_missing_origin_with_the_header_passes(bare: AsyncClient) -> None:
    response = await bare.post("/probe", json={}, headers=CSRF_HEADERS)

    assert response.status_code == 201


async def test_non_latin1_allowed_origin_configuration_does_not_crash_startup() -> None:
    app = _build_csrf_app(["https://tên.example"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        denied = await client.post(
            "/probe", json={}, headers=CSRF_HEADERS | {"Origin": "https://evil.example"}
        )

    assert denied.status_code == 403


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_safe_methods_pass_untouched(bare: AsyncClient, method: str) -> None:
    response = await bare.request(method, "/probe", headers={"Origin": "https://evil.example"})

    assert response.status_code != 403
    assert "csrf_rejected" not in response.text


async def test_the_documented_body_is_the_only_content(bare: AsyncClient) -> None:
    response = await bare.post("/probe", json={})

    assert response.headers["content-type"] == "application/json"
    assert response.content == b'{"code":"csrf_rejected","message":"Request rejected"}'


def _all_app_write_routes() -> list[tuple[str, str]]:
    app = create_app(Settings(_env_file=None, environment="development"))
    return [(method, path) for method, path, _ in served_routes(app) if method in WRITE_METHODS]


APP_WRITE_ROUTES = _all_app_write_routes()


@pytest.mark.parametrize(
    ("method", "path"),
    APP_WRITE_ROUTES,
    ids=[f"{method} {path}" for method, path in APP_WRITE_ROUTES],
)
async def test_every_served_write_route_rejects_requests_without_csrf_header(
    app: FastAPI, method: str, path: str
) -> None:
    url = path.format(
        trip_id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        expense_id=uuid.uuid4(),
        contribution_id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await client.request(method, url, json={})

    assert (response.status_code, response.json()) == (403, REJECTED)
