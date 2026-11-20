"""ASGI middleware for stripping a reverse-proxy path prefix such as ``/api``."""

from starlette.types import ASGIApp, Receive, Scope, Send


class StripPrefixMiddleware:
    """Strip a configured leading path prefix before routing when hosted without Nginx rewrite."""

    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self._prefix = prefix.rstrip("/")
        self._raw_prefix = self._prefix.encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._prefix or scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        raw_path = scope.get("raw_path")
        updated: Scope | None = None
        if path == self._prefix:
            updated = {**scope, "path": "/", "root_path": self._prefix}
            if isinstance(raw_path, bytes) and raw_path == self._raw_prefix:
                updated["raw_path"] = b"/"
        elif path.startswith(f"{self._prefix}/"):
            updated = {**scope, "path": path[len(self._prefix) :], "root_path": self._prefix}
            if isinstance(raw_path, bytes) and raw_path.startswith(self._raw_prefix + b"/"):
                updated["raw_path"] = raw_path[len(self._raw_prefix) :]

        await self.app(updated if updated is not None else scope, receive, send)
