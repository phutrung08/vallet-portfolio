from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import Device, IdempotencyKey


async def delete_dead_devices(session: AsyncSession, cutoff: datetime, limit: int) -> int:
    """Delete up to ``limit`` devices that expired or were revoked before ``cutoff``."""
    doomed = (
        select(Device.id)
        .where(or_(Device.expires_at < cutoff, Device.revoked_at < cutoff))
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(delete(Device).where(Device.id.in_(doomed)))
    return cast("CursorResult[object]", result).rowcount


async def delete_old_idempotency_keys(session: AsyncSession, cutoff: datetime, limit: int) -> int:
    """Delete up to ``limit`` idempotency keys older than ``cutoff``."""
    doomed = (
        select(IdempotencyKey.device_id, IdempotencyKey.key)
        .where(IdempotencyKey.created_at < cutoff)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    statement = delete(IdempotencyKey).where(
        tuple_(IdempotencyKey.device_id, IdempotencyKey.key).in_(doomed)
    )
    return cast("CursorResult[object]", await session.execute(statement)).rowcount
