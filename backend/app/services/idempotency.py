"""Idempotent creates: a retried create replays its stored response rather than writing twice.

The key row is inserted in the create's own transaction, before the write. If the create fails,
the key rolls back with it, so a retry runs normally. Keys belong to one device, so two devices
can neither collide nor read each other's stored responses.
"""

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import idempotency as repository
from app.services.errors import RuleViolation


@dataclass(frozen=True)
class StoredResponse:
    """Serialized response captured for an idempotent create."""

    status_code: int
    body: dict[str, object]


def request_hash(trip_id: uuid.UUID, payload: Mapping[str, object]) -> bytes:
    """Compute SHA-256 of the trip id and canonical JSON request body."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{trip_id}\n{canonical}".encode()).digest()


async def claim(
    session: AsyncSession, device_id: uuid.UUID, key: uuid.UUID, route: str, digest: bytes
) -> StoredResponse | None:
    """Claim ``key`` for writing, return its stored replay, or raise on conflict."""
    if await repository.claim(session, device_id, key, route, digest):
        return None
    used = await repository.find(session, device_id, key)
    if (
        used is None
        or used.route != route
        or used.request_hash != digest
        or used.status_code is None
        or used.response_body is None
    ):
        raise RuleViolation("idempotency_conflict")
    return StoredResponse(used.status_code, used.response_body)


async def remember(
    session: AsyncSession,
    device_id: uuid.UUID,
    key: uuid.UUID,
    response: StoredResponse,
) -> None:
    """Store the response of the claimed request before its transaction commits."""
    await repository.store_response(session, device_id, key, response.status_code, response.body)
