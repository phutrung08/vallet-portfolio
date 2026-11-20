"""Tests for Vercel environment wiring, root requirements pinning, and api/index.py."""

import base64
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.vercel_env import configure_vercel_env

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIREMENTS_TXT = REPO_ROOT / "requirements.txt"
REQUIREMENTS_LOCK = REPO_ROOT / "backend" / "requirements.lock"
API_ENTRYPOINT = REPO_ROOT / "api" / "index.py"


def test_configure_vercel_env_sets_fail_closed_defaults_and_preserves_explicit_values() -> None:
    env: dict[str, str] = {
        "POSTGRES_URL": "postgresql://fallback:secret@ep-pooler.aws.neon.tech/vallet?sslmode=require",
        "DATABASE_URL": "postgresql://primary:secret@ep-pooler.aws.neon.tech/vallet?sslmode=require",
        "VERCEL_PROJECT_PRODUCTION_URL": "vallet.vercel.app/",
        "VERCEL_BRANCH_URL": "https://vallet-git-main.vercel.app/ignored-path",
        "VERCEL_URL": "http://insecure.example.com",
    }

    configure_vercel_env(env)

    assert env["VALLET_ENVIRONMENT"] == "production"
    assert env["VALLET_COOKIE_SECURE"] == "true"
    assert env["VALLET_TRUST_PROXY_HEADERS"] == "true"
    assert env["VALLET_DB_NULL_POOL"] == "true"
    assert (
        env["VALLET_DATABASE_URL"]
        == "postgresql://primary:secret@ep-pooler.aws.neon.tech/vallet?sslmode=require"
    )
    assert json.loads(env["VALLET_ALLOWED_ORIGINS"]) == [
        "https://vallet.vercel.app",
        "https://vallet-git-main.vercel.app",
    ]
    assert "VALLET_SHARE_LINK_KEY" not in env
    assert "VALLET_BANK_DATA_KEY" not in env

    # Explicit overrides must win, and POSTGRES_URL fills when DATABASE_URL is absent.
    custom: dict[str, str] = {
        "VALLET_ENVIRONMENT": "staging",
        "VALLET_ALLOWED_ORIGINS": '["https://custom.example.com"]',
        "POSTGRES_URL": "postgresql://pg:secret@db.example.com/vallet?sslmode=require",
        "VERCEL_URL": "preview.vercel.app",
    }
    configure_vercel_env(custom)
    assert custom["VALLET_ENVIRONMENT"] == "staging"
    assert custom["VALLET_ALLOWED_ORIGINS"] == '["https://custom.example.com"]'
    assert (
        custom["VALLET_DATABASE_URL"]
        == "postgresql://pg:secret@db.example.com/vallet?sslmode=require"
    )


def test_root_requirements_pins_match_backend_requirements_lock() -> None:
    lock_pins: dict[str, str] = {}
    for line in REQUIREMENTS_LOCK.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^\\\s]+)", line)
        if match:
            lock_pins[match.group(1).lower()] = match.group(2)

    declared: dict[str, str] = {}
    for raw in REQUIREMENTS_TXT.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, _, version = stripped.partition("==")
        declared[name.lower()] = version

    assert declared, "Root requirements.txt must declare runtime pins"
    for name, version in declared.items():
        assert lock_pins.get(name) == version


@pytest.mark.anyio
async def test_api_index_entrypoint_builds_app_and_serves_prefixed_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ):
        if key.startswith(("VALLET_", "VERCEL_")) or key in {"DATABASE_URL", "POSTGRES_URL"}:
            monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://vallet_prod:secret@ep-pooler.aws.neon.tech/vallet?sslmode=require&channel_binding=require",
    )
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "vallet.vercel.app")
    monkeypatch.setenv("VALLET_SHARE_LINK_KEY", "s" * 43)
    monkeypatch.setenv("VALLET_BANK_DATA_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode())

    await dispose_engine()
    get_settings.cache_clear()
    sys.modules.pop("_vallet_vercel_index", None)
    try:
        spec = importlib.util.spec_from_file_location("_vallet_vercel_index", API_ENTRYPOINT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["_vallet_vercel_index"] = module
        spec.loader.exec_module(module)

        assert isinstance(module.app, FastAPI)
        transport = ASGITransport(app=module.app, client=("198.51.100.3", 50_000))
        async with AsyncClient(transport=transport, base_url="https://vallet.vercel.app") as client:
            response = await client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert (
            response.headers["content-security-policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )
        assert "strict-transport-security" in response.headers
    finally:
        sys.modules.pop("_vallet_vercel_index", None)
        await dispose_engine()
        get_settings.cache_clear()
