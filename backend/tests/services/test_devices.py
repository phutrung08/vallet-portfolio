from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.devices import (
    create_device,
    get_active_device,
    get_device_readonly,
    revoke_device,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)


@pytest.mark.parametrize("token", ["", "not a token", "x" * 4096, "'; DROP TABLE devices; --"])
async def test_malformed_token_never_reaches_the_database(token: str) -> None:
    # Any query on this "session" would raise AttributeError.
    no_database = cast(AsyncSession, object())

    active = await get_active_device(no_database, token, NOW, timedelta(days=1))
    readonly = await get_device_readonly(no_database, token, NOW)

    assert active is None
    assert readonly is None


async def test_readonly_lookup_does_not_slide_expiry_and_revoke_stops_lookup(
    session: AsyncSession,
) -> None:
    ttl = timedelta(days=180)
    created = create_device(session, NOW, ttl)
    await session.flush()

    later = NOW + timedelta(hours=2)
    device_id = await get_device_readonly(session, created.raw_token, later)
    assert device_id == created.device_id

    slid = await get_active_device(session, created.raw_token, later, ttl)
    assert slid is not None
    assert slid.expiry_slid is True

    await revoke_device(session, created.device_id, later)
    await session.flush()

    assert await get_device_readonly(session, created.raw_token, later) is None
    assert await get_active_device(session, created.raw_token, later, ttl) is None
