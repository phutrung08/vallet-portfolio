import base64
import os

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.pool import NullPool

from app.core.config import (
    DEV_BANK_DATA_KEY,
    DEV_ORIGIN,
    DEV_SHARE_LINK_KEY,
    LOCAL_DATABASE_URL,
    Environment,
    Settings,
    get_settings,
    normalize_asyncpg_url,
)
from app.core.db import create_engine, dispose_engine, get_engine, get_sessionmaker

GOOD_KEY = "k" * 43
GOOD_BANK_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode()
PROD_DB_URL = "postgresql+asyncpg://vallet_prod:strong-pass@db.internal:5432/vallet"
PROD_ORIGIN = "https://vallet.example.com"


def make_prod_settings(
    *,
    environment: Environment = "production",
    database_url: str = PROD_DB_URL,
    cookie_secure: bool = True,
    share_link_key: str = GOOD_KEY,
    bank_data_key: str = GOOD_BANK_KEY,
    allowed_origins: list[str] | None = None,
) -> Settings:
    return Settings(
        _env_file=None,
        environment=environment,
        database_url=database_url,
        cookie_secure=cookie_secure,
        share_link_key=SecretStr(share_link_key),
        bank_data_key=SecretStr(bank_data_key),
        allowed_origins=[PROD_ORIGIN] if allowed_origins is None else allowed_origins,
    )


@pytest.fixture(autouse=True)
def clear_vallet_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("VALLET_"):
            monkeypatch.delenv(key, raising=False)


def test_bare_settings_defaults_to_production_and_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secure_host_prefixed_cookie_is_the_default_in_development() -> None:
    settings = Settings(_env_file=None, environment="development")

    assert settings.environment == "development"
    assert settings.cookie_secure is True
    assert settings.device_cookie_name == "__Host-vl_device"
    assert settings.device_ttl_days == 180


def test_plain_cookie_name_when_not_secure_in_development() -> None:
    settings = Settings(_env_file=None, environment="development", cookie_secure=False)

    assert settings.device_cookie_name == "vl_device"


def test_development_may_use_dev_defaults_and_caches_bank_key_bytes() -> None:
    settings = Settings(_env_file=None, environment="development")

    assert settings.share_link_key.get_secret_value() == DEV_SHARE_LINK_KEY
    assert settings.bank_data_key.get_secret_value() == DEV_BANK_DATA_KEY
    assert settings.bank_data_key_bytes is settings.bank_data_key_bytes
    assert len(settings.bank_data_key_bytes) == 32


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_non_dev_environments_accept_complete_hardened_settings(
    environment: Environment,
) -> None:
    settings = make_prod_settings(environment=environment)

    assert settings.environment == environment
    assert settings.share_link_key_bytes == GOOD_KEY.encode()
    assert settings.bank_data_key_bytes == bytes(range(32))


@pytest.mark.parametrize("key", [DEV_SHARE_LINK_KEY, "k" * 31, ""])
def test_production_refuses_dev_or_short_share_key(key: str) -> None:
    with pytest.raises(ValidationError, match="SHARE_LINK_KEY"):
        make_prod_settings(share_link_key=key)


def test_staging_refuses_default_share_key() -> None:
    with pytest.raises(ValidationError, match="SHARE_LINK_KEY"):
        Settings(
            _env_file=None,
            environment="staging",
            database_url=PROD_DB_URL,
            cookie_secure=True,
            bank_data_key=SecretStr(GOOD_BANK_KEY),
            allowed_origins=[PROD_ORIGIN],
        )


def test_production_refuses_the_dev_bank_key() -> None:
    with pytest.raises(ValidationError, match="BANK_DATA_KEY must not be the dev key"):
        make_prod_settings(bank_data_key=DEV_BANK_DATA_KEY)


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize(
    "key",
    [
        base64.urlsafe_b64encode(b"k" * 31).decode(),
        base64.urlsafe_b64encode(b"k" * 48).decode(),
        "k" * 43 + "!",
        "",
    ],
    ids=["short", "long", "not base64url", "empty"],
)
def test_a_malformed_bank_key_is_refused_everywhere(environment: Environment, key: str) -> None:
    with pytest.raises(ValidationError, match="BANK_DATA_KEY must be 32 random bytes") as raised:
        make_prod_settings(environment=environment, bank_data_key=key)

    assert key not in str(raised.value) or key == ""


def test_production_refuses_insecure_cookies() -> None:
    with pytest.raises(ValidationError, match="VALLET_COOKIE_SECURE"):
        make_prod_settings(cookie_secure=False)


@pytest.mark.parametrize(
    "database_url",
    [
        LOCAL_DATABASE_URL,
        "postgresql+asyncpg://prod:secret@localhost:5432/vallet",
        "postgresql+asyncpg://prod:secret@127.0.0.1:5432/vallet",
        "postgresql+asyncpg://prod:secret@[::1]:5432/vallet",
        "postgresql+asyncpg://vallet:vallet_dev@db.internal:5432/vallet",
    ],
)
def test_production_refuses_dev_or_loopback_database_urls(database_url: str) -> None:
    with pytest.raises(ValidationError, match="VALLET_DATABASE_URL"):
        make_prod_settings(database_url=database_url)


@pytest.mark.parametrize(
    "origins",
    [
        [],
        [DEV_ORIGIN],
        ["http://app.example.com"],
        [PROD_ORIGIN, "http://staging.example.com"],
    ],
)
def test_production_refuses_empty_dev_or_non_https_origins(origins: list[str]) -> None:
    with pytest.raises(ValidationError, match="VALLET_ALLOWED_ORIGINS"):
        make_prod_settings(allowed_origins=origins)


def test_unknown_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALLET_ENVIRONMENT", "qa")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_allowed_origins_default_to_dev_origin_and_read_json_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings(_env_file=None, environment="development").allowed_origins == [DEV_ORIGIN]

    monkeypatch.setenv("VALLET_ALLOWED_ORIGINS", '["https://app.example.com"]')
    assert Settings(_env_file=None, environment="development").allowed_origins == [
        "https://app.example.com"
    ]


def test_proxy_headers_are_untrusted_unless_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(_env_file=None, environment="development").trust_proxy_headers is False

    monkeypatch.setenv("VALLET_TRUST_PROXY_HEADERS", "true")
    assert Settings(_env_file=None, environment="development").trust_proxy_headers is True


def test_rejected_keys_and_secrets_are_not_echoed() -> None:
    with pytest.raises(ValidationError) as raised:
        make_prod_settings(share_link_key="SHORTSECRET")

    assert "SHORTSECRET" not in str(raised.value)
    settings = make_prod_settings()
    assert GOOD_KEY not in repr(settings)
    assert GOOD_BANK_KEY not in repr(settings)


@pytest.mark.anyio
async def test_dispose_engine_is_safe_before_and_after_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
    await dispose_engine()

    monkeypatch.setenv("VALLET_ENVIRONMENT", "development")
    engine = get_engine()
    _ = get_sessionmaker()
    assert get_engine.cache_info().currsize == 1

    await dispose_engine()

    assert get_engine.cache_info().currsize == 0
    assert get_sessionmaker.cache_info().currsize == 0
    assert engine is not get_engine()
    await dispose_engine()
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://user:p%40ss@ep-host-pooler.aws.neon.tech/vallet?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://user:p%40ss@ep-host-pooler.aws.neon.tech/vallet?ssl=require",
        ),
        (
            "postgres://user:pass@db.example.com:5432/vallet?sslmode=verify-full",
            "postgresql+asyncpg://user:pass@db.example.com:5432/vallet?ssl=verify-full",
        ),
        (
            "postgresql://user:pass@db.example.com/vallet?ssl=disable&sslmode=require",
            "postgresql+asyncpg://user:pass@db.example.com/vallet?ssl=disable",
        ),
        (
            "postgresql+asyncpg://user:pass@db.example.com/vallet?ssl=require",
            "postgresql+asyncpg://user:pass@db.example.com/vallet?ssl=require",
        ),
    ],
)
def test_normalize_asyncpg_url_adapts_neon_and_libpq_urls(raw: str, expected: str) -> None:
    assert normalize_asyncpg_url(raw) == expected


def test_settings_normalizes_neon_url_while_still_rejecting_loopback_in_production() -> None:
    neon_url = "postgresql://vallet_app:secret@ep-demo.aws.neon.tech/vallet?sslmode=require&channel_binding=require"
    settings = make_prod_settings(database_url=neon_url)
    assert (
        settings.database_url
        == "postgresql+asyncpg://vallet_app:secret@ep-demo.aws.neon.tech/vallet?ssl=require"
    )

    with pytest.raises(ValidationError, match="VALLET_DATABASE_URL"):
        make_prod_settings(database_url="postgresql://prod:secret@localhost:5432/vallet")


@pytest.mark.anyio
async def test_db_null_pool_setting_builds_null_pool_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
    try:
        monkeypatch.setenv("VALLET_ENVIRONMENT", "development")
        monkeypatch.setenv("VALLET_DB_NULL_POOL", "true")
        engine = get_engine()
        assert isinstance(engine.pool, NullPool)

        pooled = create_engine(LOCAL_DATABASE_URL, null_pool=False)
        assert not isinstance(pooled.pool, NullPool)
        await pooled.dispose()
    finally:
        await dispose_engine()
        get_settings.cache_clear()
