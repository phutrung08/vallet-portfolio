"""Verify no tokens, cookies, request bodies, or SQL bound parameters reach logs."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core import db
from app.core.config import Settings
from app.core.logging import configure_logging
from tests.api.conftest import CSRF_HEADERS
from tests.api.test_join import join
from tests.api.test_join_preview import shared_trip
from tests.db.database import database_url_for_tests

pytestmark = pytest.mark.anyio


async def test_the_500_log_line_has_method_and_path_only(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url="https://test", headers=CSRF_HEADERS
    ) as client:
        response = await client.request(
            "GET",
            "/_test/boom?token=QUERYSECRET",
            content=b"BODYSECRET",
            headers={"Cookie": "vl_device=COOKIESECRET", "Authorization": "Bearer AUTHSECRET"},
        )

    assert response.status_code == 500
    (record,) = [r for r in caplog.records if r.name == "app.api.errors"]
    assert record.getMessage() == "Unhandled error on GET /_test/boom"
    for secret in ("QUERYSECRET", "BODYSECRET", "COOKIESECRET", "AUTHSECRET"):
        assert secret not in caplog.text


async def test_a_join_token_never_reaches_the_logs(
    client: AsyncClient,
    other_client: AsyncClient,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    configure_logging()
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]
    wrong_token = token[::-1]

    preview = await other_client.post("/join/preview", json={"token": token})
    failing = await join(other_client, wrong_token, member_id=binh)
    malformed = await join(other_client, "not a token", member_id=binh)
    joined = await join(other_client, token, member_id=binh)

    assert [r.status_code for r in (preview, failing, malformed, joined)] == [200, 404, 404, 200]
    secrets = [token, wrong_token, other_client.cookies[settings.device_cookie_name]]
    assert caplog.records
    for secret in secrets:
        assert secret not in caplog.text
        assert all(secret not in record.getMessage() for record in caplog.records)


async def test_the_production_engine_hides_bound_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev_settings = Settings(_env_file=None, environment="development")
    db.get_engine.cache_clear()
    monkeypatch.setattr(db, "get_settings", lambda: dev_settings)
    try:
        assert db.get_engine().sync_engine.hide_parameters is True
    finally:
        await db.dispose_engine()
    assert db.create_engine("postgresql+asyncpg://u:p@127.0.0.1:1/x").sync_engine.hide_parameters


async def test_a_sql_error_does_not_echo_its_parameters(db_engine: AsyncEngine) -> None:
    engine = db.create_engine(database_url_for_tests().render_as_string(hide_password=False))
    statement = text("SELECT CAST(:value AS integer) / (CAST(:value AS integer) - :value)")
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as raised:
                await connection.execute(statement, {"value": 31337})
    finally:
        await engine.dispose()

    assert "division by zero" in str(raised.value)
    assert "31337" not in str(raised.value)
