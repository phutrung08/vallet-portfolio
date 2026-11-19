"""CSRF defense for state-changing requests.

A cross-site page cannot add a custom header without a CORS preflight, which this API never
approves, so the header alone stops forged form posts and simple requests. The Origin check adds
a second, independent barrier for browsers: any request carrying a foreign Origin is refused.
"""

from collections.abc import Collection

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.errors import error_response

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_HEADER = b"x-requested-with"
CSRF_HEADER_VALUE = b"vallet"
ORIGIN_HEADER = b"origin"


class CsrfMiddleware:
    """ASGI middleware requiring custom marker header and allowed Origin on write methods."""

    def __init__(self, app: ASGIApp, allowed_origins: Collection[str]) -> None:
        self.app = app
        self._allowed_origins = frozenset(origin.encode("utf-8") for origin in allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in WRITE_METHODS and self._rejects(scope):
            response = error_response(403, "csrf_rejected", "Request rejected")
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _rejects(self, scope: Scope) -> bool:
        headers = scope["headers"]
        marker = [value for name, value in headers if name == CSRF_HEADER]
        origins = [value for name, value in headers if name == ORIGIN_HEADER]
        return marker != [CSRF_HEADER_VALUE] or not self._allowed_origins.issuperset(origins)
