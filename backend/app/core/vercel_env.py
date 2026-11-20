"""Environment defaults and Vercel/Neon adapter helpers for serverless deployments."""

import json
from collections.abc import MutableMapping
from urllib.parse import urlsplit


def _has_value(env: MutableMapping[str, str], key: str) -> bool:
    return bool(env.get(key, "").strip())


def _normalize_vercel_origin(raw: str) -> str | None:
    candidate = raw.strip().rstrip("/")
    if not candidate or candidate.lower().startswith("http://"):
        return None
    if not candidate.lower().startswith("https://"):
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return None
    return f"https://{parsed.netloc}"


def configure_vercel_env(env: MutableMapping[str, str]) -> None:
    """Populate safe serverless ``VALLET_*`` defaults from Vercel and Postgres env vars.

    Explicitly configured ``VALLET_*`` values are preserved, and cryptographic keys
    (``VALLET_SHARE_LINK_KEY``, ``VALLET_BANK_DATA_KEY``) are never defaulted.
    """
    env.setdefault("VALLET_ENVIRONMENT", "production")
    env.setdefault("VALLET_COOKIE_SECURE", "true")
    env.setdefault("VALLET_TRUST_PROXY_HEADERS", "true")
    env.setdefault("VALLET_DB_NULL_POOL", "true")

    if not _has_value(env, "VALLET_DATABASE_URL"):
        for fallback in ("DATABASE_URL", "POSTGRES_URL"):
            value = env.get(fallback, "").strip()
            if value:
                env["VALLET_DATABASE_URL"] = value
                break

    if not _has_value(env, "VALLET_ALLOWED_ORIGINS"):
        origins: list[str] = []
        for var in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL"):
            origin = _normalize_vercel_origin(env.get(var, ""))
            if origin and origin not in origins:
                origins.append(origin)
        if origins:
            env["VALLET_ALLOWED_ORIGINS"] = json.dumps(origins)
