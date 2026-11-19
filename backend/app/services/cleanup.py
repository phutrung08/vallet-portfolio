from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import cleanup as repository

# A device that lapsed or was signed out stays this long so support can tell why a session stopped.
DEVICE_GRACE = timedelta(days=30)
# Longer than any client retries a create, so no live retry can hit a deleted key.
IDEMPOTENCY_TTL = timedelta(hours=24)
BATCH_SIZE = 1_000


@dataclass(frozen=True)
class CleanupCounts:
    devices: int
    idempotency_keys: int


async def _drain(
    session: AsyncSession,
    delete_batch: Callable[[AsyncSession, datetime, int], Awaitable[int]],
    cutoff: datetime,
    batch_size: int,
) -> int:
    total = 0
    while True:
        deleted = await delete_batch(session, cutoff, batch_size)
        # One transaction per batch, so no statement holds its row locks for long.
        await session.commit()
        total += deleted
        if deleted < batch_size:
            return total


async def delete_expired_data(
    session: AsyncSession, now: datetime, batch_size: int = BATCH_SIZE
) -> CleanupCounts:
    """Delete dead devices (with their memberships) and old idempotency keys, in batches."""
    keys = await _drain(
        session, repository.delete_old_idempotency_keys, now - IDEMPOTENCY_TTL, batch_size
    )
    devices = await _drain(session, repository.delete_dead_devices, now - DEVICE_GRACE, batch_size)
    return CleanupCounts(devices=devices, idempotency_keys=keys)
