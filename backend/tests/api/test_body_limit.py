import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.body_limit import BodyLimitMiddleware
from app.api.errors import register_error_handlers
from app.core.limits import MAX_REQUEST_BODY_BYTES

pytestmark = pytest.mark.anyio

TOO_LARGE = {"code": "payload_too_large", "message": "Request too large"}
JSON = {"Content-Type": "application/json"}
CHUNK = 1024


class ProbeBody(BaseModel):
    name: str


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)
    register_error_handlers(app, hsts=True)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/probe", status_code=201)
    def probe(payload: ProbeBody) -> dict[str, str]:
        return {"name": payload.name}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        yield client


def test_the_cap_is_64_kib() -> None:
    assert MAX_REQUEST_BODY_BYTES == 64 * 1024


async def test_a_declared_length_over_the_cap_is_413(client: AsyncClient) -> None:
    response = await client.post(
        "/probe", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1), headers=JSON
    )

    assert (response.status_code, response.json()) == (413, TOO_LARGE)
    assert response.content == b'{"code":"payload_too_large","message":"Request too large"}'


async def test_a_body_at_the_cap_reaches_the_parser(client: AsyncClient) -> None:
    response = await client.post("/probe", content=b"x" * MAX_REQUEST_BODY_BYTES, headers=JSON)

    assert response.status_code == 422


async def test_a_declared_body_over_the_cap_is_refused_before_it_is_parsed(
    client: AsyncClient,
) -> None:
    oversized = json.dumps({"name": "x" * MAX_REQUEST_BODY_BYTES}).encode()

    response = await client.post("/probe", content=oversized, headers=JSON)

    assert (response.status_code, response.json()) == (413, TOO_LARGE)


async def test_a_streamed_body_over_the_cap_is_413_and_cut_off_early(
    client: AsyncClient,
) -> None:
    sent = 0

    async def chunks() -> AsyncIterator[bytes]:
        nonlocal sent
        for _ in range(MAX_REQUEST_BODY_BYTES // CHUNK * 4):
            sent += 1
            yield b"x" * CHUNK

    response = await client.post("/probe", content=chunks(), headers=JSON)

    assert "content-length" not in response.request.headers
    assert (response.status_code, response.json()) == (413, TOO_LARGE)
    assert sent == MAX_REQUEST_BODY_BYTES // CHUNK + 1


async def test_a_streamed_body_within_the_cap_passes(client: AsyncClient) -> None:
    payload = json.dumps({"name": "Trip"}).encode()

    async def chunks() -> AsyncIterator[bytes]:
        yield payload[:5]
        yield payload[5:]

    response = await client.post("/probe", content=chunks(), headers=JSON)

    assert "content-length" not in response.request.headers
    assert response.status_code == 201


async def test_the_app_still_answers_after_a_rejected_body(client: AsyncClient) -> None:
    await client.post("/probe", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1), headers=JSON)

    assert (await client.get("/health")).status_code == 200
