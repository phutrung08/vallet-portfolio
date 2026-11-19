from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, PrivateAttr, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.crypto import parse_key

Environment = Literal["development", "staging", "production"]

LOCAL_DATABASE_URL = "postgresql+asyncpg://vallet:vallet_dev@127.0.0.1:5433/vallet"
# Development only: anyone can read this, so it must never derive links outside development.
DEV_SHARE_LINK_KEY = "dev-only-share-link-key-not-for-production-use-0000"
MIN_SHARE_LINK_KEY_BYTES = 32
# Development only, and public: base64url of b"dev-only-bank-key-not-for-prod!!".
DEV_BANK_DATA_KEY = "ZGV2LW9ubHktYmFuay1rZXktbm90LWZvci1wcm9kISE"
DEV_ORIGIN = "http://localhost:5173"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class Settings(BaseSettings):
    """Application settings loaded from ``VALLET_*`` env vars with fail-closed defaults."""

    # Hidden input: a rejected key must not be echoed into the startup error.
    model_config = SettingsConfigDict(
        env_prefix="VALLET_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    app_name: str = "Vallet"
    environment: Environment = "production"
    database_url: str = LOCAL_DATABASE_URL
    cookie_secure: bool = True
    device_ttl_days: int = Field(default=180, ge=1)
    share_link_key: SecretStr = SecretStr(DEV_SHARE_LINK_KEY)
    # 32 random bytes, base64url: the AES-256-GCM key for bank account numbers.
    bank_data_key: SecretStr = SecretStr(DEV_BANK_DATA_KEY)
    # Origins whose pages may call the API; exact match on scheme, host and port.
    allowed_origins: list[str] = Field(default_factory=lambda: [DEV_ORIGIN])
    # Rate limits key on the last X-Forwarded-For hop instead of the socket address. Only true
    # behind a reverse proxy that sets that header; otherwise any client could pick its own key.
    trust_proxy_headers: bool = False
    _bank_data_key_bytes: bytes = PrivateAttr(default=b"")

    @model_validator(mode="after")
    def _require_real_share_link_key(self) -> Self:
        key = self.share_link_key.get_secret_value()
        weak = key == DEV_SHARE_LINK_KEY or len(key.encode()) < MIN_SHARE_LINK_KEY_BYTES
        if self.environment != "development" and weak:
            raise ValueError(
                "VALLET_SHARE_LINK_KEY must be a random value of at least 32 bytes "
                "outside development"
            )
        return self

    @model_validator(mode="after")
    def _require_real_bank_data_key(self) -> Self:
        # A malformed key can never encrypt anything, so it is refused in development too.
        key = self.bank_data_key.get_secret_value()
        try:
            self._bank_data_key_bytes = parse_key(key)
        except ValueError:
            raise ValueError(
                "VALLET_BANK_DATA_KEY must be 32 random bytes, base64url-encoded"
            ) from None
        if self.environment != "development" and key == DEV_BANK_DATA_KEY:
            raise ValueError("VALLET_BANK_DATA_KEY must not be the dev key outside development")
        return self

    @model_validator(mode="after")
    def _require_safe_non_dev_transport_and_db(self) -> Self:
        if self.environment == "development":
            return self
        if not self.cookie_secure:
            raise ValueError("VALLET_COOKIE_SECURE must be true outside development")
        parsed_db = urlsplit(self.database_url)
        host = (parsed_db.hostname or "").lower()
        if (
            self.database_url == LOCAL_DATABASE_URL
            or host in _LOOPBACK_HOSTS
            or "vallet_dev" in self.database_url
        ):
            raise ValueError(
                "VALLET_DATABASE_URL must not use development defaults or loopback hosts "
                "outside development"
            )
        if not self.allowed_origins or any(
            origin == DEV_ORIGIN or not origin.startswith("https://")
            for origin in self.allowed_origins
        ):
            raise ValueError(
                "VALLET_ALLOWED_ORIGINS must contain only HTTPS origins outside development"
            )
        return self

    @property
    def bank_data_key_bytes(self) -> bytes:
        """Return the validated and cached 32-byte AES-256-GCM bank data key."""
        return self._bank_data_key_bytes

    @property
    def share_link_key_bytes(self) -> bytes:
        """Return the raw bytes used to derive HMAC share tokens."""
        return self.share_link_key.get_secret_value().encode()

    @property
    def device_cookie_name(self) -> str:
        # Browsers accept a __Host- cookie only if it is Secure, Path=/ and has no Domain, so
        # a sibling subdomain cannot plant or overwrite it.
        return "__Host-vl_device" if self.cookie_secure else "vl_device"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application ``Settings`` instance."""
    return Settings()
