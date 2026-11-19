from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import devices, health, trips
from app.api.body_limit import BodyLimitMiddleware
from app.api.csrf import CsrfMiddleware
from app.api.errors import register_error_handlers
from app.api.rate_limit import RateLimitMiddleware
from app.api.security_headers import SecurityHeadersMiddleware
from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.limits import MAX_REQUEST_BODY_BYTES
from app.core.logging import configure_logging


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application instance."""
    configure_logging()
    resolved = settings or get_settings()
    docs_enabled = resolved.environment == "development"
    application = FastAPI(
        title=resolved.app_name,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=_lifespan,
    )
    # Last added runs first: SecurityHeaders wraps RateLimit, BodyLimit, and Csrf.
    # Unhandled 500s handled by Starlette's ServerErrorMiddleware also receive security headers
    # from register_error_handlers().
    application.add_middleware(CsrfMiddleware, allowed_origins=resolved.allowed_origins)
    application.add_middleware(BodyLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)
    application.add_middleware(
        RateLimitMiddleware, trust_proxy_headers=resolved.trust_proxy_headers
    )
    application.add_middleware(SecurityHeadersMiddleware, hsts=resolved.cookie_secure)
    register_error_handlers(application, hsts=resolved.cookie_secure)
    application.include_router(health.router)
    application.include_router(devices.router)
    application.include_router(trips.router)
    return application


def __getattr__(name: str) -> FastAPI:
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
