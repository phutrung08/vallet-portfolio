"""Security headers on every API response.

The API only ever answers JSON, so its CSP allows nothing and no page may frame it. The
frontend's own CSP is set by its static host or reverse proxy. HSTS goes out only when cookies
are Secure, which is the signal that the API is served over HTTPS.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-site",
}
HSTS = ("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def security_headers_dict(*, hsts: bool) -> dict[str, str]:
    """Build the API response security headers dictionary."""
    headers = dict(API_HEADERS)
    if hsts:
        headers[HSTS[0]] = HSTS[1]
    return headers


class SecurityHeadersMiddleware:
    """ASGI middleware that attaches standard security headers to every HTTP response."""

    def __init__(self, app: ASGIApp, hsts: bool) -> None:
        self.app = app
        self._headers = security_headers_dict(hsts=hsts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._headers.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
