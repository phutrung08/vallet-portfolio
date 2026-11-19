import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import IdempotencyKey


async def claim(
    session: AsyncSession, device_id: uuid.UUID, key: uuid.UUID, route: str, request_hash: bytes
) -> bool:
    """Insert the key row; return False when the device already used ``key``."""
    statement = (
        insert(IdempotencyKey)
        .values(device_id=device_id, key=key, route=route, request_hash=request_hash)
        .on_conflict_do_nothing(index_elements=[IdempotencyKey.device_id, IdempotencyKey.key])
        .returning(IdempotencyKey.key)
    )
    return await session.scalar(statement) is not None


async def find(
    session: AsyncSession, device_id: uuid.UUID, key: uuid.UUID
) -> IdempotencyKey | None:
    statement = select(IdempotencyKey).where(
        IdempotencyKey.device_id == device_id, IdempotencyKey.key == key
    )
    return await session.scalar(statement)


async def store_response(
    session: AsyncSession,
    device_id: uuid.UUID,
    key: uuid.UUID,
    status_code: int,
    body: dict[str, object],
) -> None:
    statement = (
        update(IdempotencyKey)
        .where(IdempotencyKey.device_id == device_id, IdempotencyKey.key == key)
        .values(status_code=status_code, response_body=body)
    )
    await session.execute(statement)
