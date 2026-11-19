"""Cap the request body before anything parses it.

A declared ``Content-Length`` over the cap is refused without reading a byte. A body with no
declared length (chunked) is counted as it streams; the first chunk that pushes the total over
the cap is not passed on, the 413 goes out and the app sees a disconnect instead of the body.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_response


class BodyLimitMiddleware:
    """ASGI middleware enforcing a hard request payload size ceiling."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self._declared_length(scope) > self._max_bytes:
            await self._reject(scope, receive, send)
            return
        await self._counted(scope, receive, send)

    @staticmethod
    def _declared_length(scope: Scope) -> int:
        for name, value in scope["headers"]:
            if name == b"content-length":
                return int(value) if value.isdigit() else 0
        return 0

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(413, "payload_too_large", "Request too large")
        await response(scope, receive, send)

    async def _counted(self, scope: Scope, receive: Receive, send: Send) -> None:
        received = 0
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    rejected = True
                    await self._reject(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not rejected:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            # After the cut-off the app can only fail because it lost its body; 413 is sent.
            if not rejected:
                raise
