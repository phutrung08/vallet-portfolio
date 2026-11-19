import base64
import os

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError

from app import main
from app.core.config import Settings, get_settings
from app.main import create_app


def _clear_vallet_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("VALLET_"):
            monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_health_returns_ok_and_lifespan_cleans_up() -> None:
    settings = Settings(_env_file=None, environment="development", cookie_secure=False)
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client,
    ):
        response = await client.get("/health")
        docs = await client.get("/docs")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert docs.status_code == 200


@pytest.mark.anyio
async def test_docs_are_disabled_outside_development() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+asyncpg://prod:secret@db.internal:5432/vallet",
        cookie_secure=True,
        share_link_key=SecretStr("k" * 43),
        bank_data_key=SecretStr(base64.urlsafe_b64encode(bytes(range(32))).decode()),
        allowed_origins=["https://vallet.example.com"],
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client,
    ):
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404


def test_create_app_fails_closed_when_environment_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_vallet_env(monkeypatch)
    with pytest.raises(ValidationError):
        create_app()
    with pytest.raises(ValidationError):
        _ = main.app
    get_settings.cache_clear()
