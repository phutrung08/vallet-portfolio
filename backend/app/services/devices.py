import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token, is_well_formed_token, new_token
from app.repositories import devices as repository
from app.repositories.models import Device

# Sliding the expiry on every request would turn every read into a write.
REFRESH_INTERVAL = timedelta(hours=1)


@dataclass(frozen=True)
class DeviceSession:
    """Validated device identifier plus whether its cookie expiry just slid."""

    device_id: uuid.UUID
    expiry_slid: bool


@dataclass(frozen=True)
class CreatedDevice:
    """Newly created device identifier paired with its one-time raw cookie token."""

    device_id: uuid.UUID
    raw_token: str


async def _find_device(session: AsyncSession, raw_token: str, now: datetime) -> Device | None:
    if not is_well_formed_token(raw_token):
        return None
    return await repository.find_active_device(session, hash_token(raw_token), now)


async def get_active_device(
    session: AsyncSession, raw_token: str, now: datetime, ttl: timedelta
) -> DeviceSession | None:
    """Return the active device for ``raw_token``, sliding its expiry when due."""
    device = await _find_device(session, raw_token, now)
    if device is None:
        return None
    due = now - device.last_seen_at >= REFRESH_INTERVAL
    if due:
        device.last_seen_at = now
        device.expires_at = now + ttl
    return DeviceSession(device_id=device.id, expiry_slid=due)


async def get_device_readonly(
    session: AsyncSession, raw_token: str, now: datetime
) -> uuid.UUID | None:
    """Return the active device id without sliding its expiry (used for sign-out)."""
    device = await _find_device(session, raw_token, now)
    return None if device is None else device.id


def create_device(session: AsyncSession, now: datetime, ttl: timedelta) -> CreatedDevice:
    """Create a new device session row and return its id and raw cookie token."""
    raw_token = new_token()
    device = repository.add_device(session, hash_token(raw_token), now, now + ttl)
    return CreatedDevice(device_id=device.id, raw_token=raw_token)


async def get_membership(
    session: AsyncSession, device_id: uuid.UUID, trip_id: uuid.UUID
) -> uuid.UUID | None:
    """Return the active member id for ``device_id`` in ``trip_id``, if any."""
    membership = await repository.find_active_membership(session, device_id, trip_id)
    return None if membership is None else membership.member_id


async def revoke_device(session: AsyncSession, device_id: uuid.UUID, now: datetime) -> None:
    """Revoke ``device_id`` at ``now``."""
    await repository.revoke_device(session, device_id, now)
