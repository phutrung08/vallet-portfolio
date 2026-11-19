"""The ``Idempotency-Key`` header for creates that record money.

The header is optional; when present it must be a UUID. A replay answers with the stored status
and body plus ``Idempotent-Replayed: true``, and writes nothing.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, MemberContext, TripMember
from app.services import idempotency
from app.services.idempotency import StoredResponse

REPLAYED_HEADER = "Idempotent-Replayed"


@dataclass(frozen=True)
class IdempotentWrite:
    """Helper wrapping one idempotent create invocation scoped to ``caller.device_id``."""

    session: AsyncSession
    caller: MemberContext
    key: UUID | None
    route: str
    status_code: int
    response: Response

    async def run[T: BaseModel](
        self, body: BaseModel, out: type[T], write: Callable[[], Awaitable[T]]
    ) -> T:
        """Run ``write()`` once per key; replay the stored response on retries."""
        if self.key is None:
            return await write()
        device_id = self.caller.device_id
        digest = idempotency.request_hash(self.caller.trip_id, body.model_dump(mode="json"))
        stored = await idempotency.claim(self.session, device_id, self.key, self.route, digest)
        if stored is not None:
            self.response.status_code = stored.status_code
            self.response.headers[REPLAYED_HEADER] = "true"
            return out.model_validate(stored.body)
        result = await write()
        response = StoredResponse(self.status_code, result.model_dump(mode="json"))
        await idempotency.remember(self.session, device_id, self.key, response)
        return result


def idempotent_write(
    request: Request,
    response: Response,
    session: DbSession,
    caller: TripMember,
    idempotency_key: Annotated[UUID | None, Header()] = None,
) -> IdempotentWrite:
    """Resolve an ``IdempotentWrite`` helper for the current API route."""
    route = request.scope.get("route")
    if not isinstance(route, APIRoute):
        raise TypeError("IdempotentCreate can only be used on an APIRoute")
    return IdempotentWrite(
        session=session,
        caller=caller,
        key=idempotency_key,
        route=f"{request.method} {route.path}",
        status_code=route.status_code or 200,
        response=response,
    )


IdempotentCreate = Annotated[IdempotentWrite, Depends(idempotent_write)]
