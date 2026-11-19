"""Request-scoped dependencies: the database unit of work, device session, trip membership."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_readonly_session, get_session
from app.services import devices


async def get_db(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[AsyncSession]:
    """Yield a transactional database session and map deferred FK conflicts to 409."""
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    try:
        await session.commit()
    except IntegrityError as error:
        # Member FKs are deferred, so a bad reference only shows up here.
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT) from error


def get_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


# scope="function" commits before the response is sent, so a failed commit still becomes 409.
DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]
ReadonlySnapshot = Annotated[AsyncSession, Depends(get_readonly_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Now = Annotated[datetime, Depends(get_now)]


def _device_ttl(settings: Settings) -> timedelta:
    return timedelta(days=settings.device_ttl_days)


def _set_device_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.device_cookie_name,
        raw_token,
        max_age=int(_device_ttl(settings).total_seconds()),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_device_cookie(response: Response, settings: Settings) -> None:
    """Expire the device session cookie on sign-out."""
    response.delete_cookie(
        settings.device_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


async def optional_device(
    request: Request, response: Response, session: DbSession, settings: AppSettings, now: Now
) -> UUID | None:
    """Resolve the active device id from the cookie, sliding expiry if due."""
    raw_token = request.cookies.get(settings.device_cookie_name)
    if raw_token is None:
        return None
    active = await devices.get_active_device(session, raw_token, now, _device_ttl(settings))
    if active is None:
        return None
    if active.expiry_slid:
        _set_device_cookie(response, raw_token, settings)
    return active.device_id


OptionalDeviceId = Annotated[UUID | None, Depends(optional_device)]


async def optional_device_readonly(
    request: Request, session: DbSession, settings: AppSettings, now: Now
) -> UUID | None:
    """Resolve the active device id without sliding expiry or setting cookies."""
    raw_token = request.cookies.get(settings.device_cookie_name)
    if raw_token is None:
        return None
    return await devices.get_device_readonly(session, raw_token, now)


ReadonlyDeviceId = Annotated[UUID | None, Depends(optional_device_readonly)]


def ensure_device(
    device_id: OptionalDeviceId,
    response: Response,
    session: DbSession,
    settings: AppSettings,
    now: Now,
) -> UUID:
    """Return the caller's active device id or mint a fresh device session cookie."""
    if device_id is not None:
        return device_id
    created = devices.create_device(session, now, _device_ttl(settings))
    _set_device_cookie(response, created.raw_token, settings)
    return created.device_id


@dataclass(frozen=True)
class MemberContext:
    """Authenticated caller context within a specific trip."""

    device_id: UUID
    trip_id: UUID
    member_id: UUID


async def require_member(
    trip_id: Annotated[UUID, Path()], device_id: OptionalDeviceId, session: DbSession
) -> MemberContext:
    """Authorize an active member of ``trip_id``, returning 404 uniformly on failure."""
    # One 404 for "no session", "not your trip" and "no such trip", so trip ids cannot be probed.
    if device_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    member_id = await devices.get_membership(session, device_id, trip_id)
    if member_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return MemberContext(device_id=device_id, trip_id=trip_id, member_id=member_id)


TripMember = Annotated[MemberContext, Depends(require_member)]
