from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    AppSettings,
    DbSession,
    Now,
    OptionalDeviceId,
    TripMember,
    ensure_device,
)
from app.api.schemas.trips import (
    CreateTripRequest,
    ShareLinkOut,
    TripDetailOut,
    TripListOut,
)
from app.services import trips
from app.services.trips import NewTrip

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_trip(
    body: CreateTripRequest,
    session: DbSession,
    settings: AppSettings,
    device_id: Annotated[UUID, Depends(ensure_device)],
) -> TripDetailOut:
    """Create a trip and attach the caller's device to its creator member."""
    detail = await trips.create_trip(
        session, device_id, settings.share_link_key_bytes, NewTrip(**body.model_dump())
    )
    return TripDetailOut.model_validate(detail)


@router.get("")
async def list_trips(session: DbSession, device_id: OptionalDeviceId) -> TripListOut:
    """List every active trip attached to the current device."""
    summaries = await trips.list_trips(session, device_id)
    return TripListOut.model_validate({"trips": summaries})


@router.get("/{trip_id}")
async def get_trip(member: TripMember, session: DbSession) -> TripDetailOut:
    """Return full trip details for an authorized member."""
    detail = await trips.get_trip_detail(session, member.trip_id, member.member_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TripDetailOut.model_validate(detail)


@router.get("/{trip_id}/share-link")
async def get_share_link(
    member: TripMember, session: DbSession, settings: AppSettings, response: Response
) -> ShareLinkOut:
    """Return the active invite token for this trip."""
    link = await trips.get_share_link(session, settings.share_link_key_bytes, member.trip_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    response.headers["Cache-Control"] = "no-store"
    return ShareLinkOut.model_validate(link)


@router.post("/{trip_id}/share-link/rotate")
async def rotate_share_link(
    member: TripMember, session: DbSession, settings: AppSettings, response: Response, now: Now
) -> ShareLinkOut:
    """Replace the share link; existing members keep access while old tokens return 404."""
    link = await trips.rotate_share_link(
        session, settings.share_link_key_bytes, member.trip_id, member.member_id, now
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    response.headers["Cache-Control"] = "no-store"
    return ShareLinkOut.model_validate(link)


@router.post("/{trip_id}/close")
async def close_trip(member: TripMember, session: DbSession, now: Now) -> TripDetailOut:
    """Close the trip against new expenses and fund changes while allowing settlement."""
    detail = await trips.close_trip(session, member.trip_id, member.member_id, now)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TripDetailOut.model_validate(detail)


@router.post("/{trip_id}/reopen")
async def reopen_trip(member: TripMember, session: DbSession, now: Now) -> TripDetailOut:
    """Reopen a previously closed trip."""
    detail = await trips.reopen_trip(session, member.trip_id, member.member_id, now)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TripDetailOut.model_validate(detail)


@router.post("/{trip_id}/lock")
async def lock_trip(member: TripMember, session: DbSession, now: Now) -> TripDetailOut:
    """Make the trip read-only for everyone until unlocked."""
    detail = await trips.lock_trip(session, member.trip_id, member.member_id, now)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TripDetailOut.model_validate(detail)


@router.post("/{trip_id}/unlock")
async def unlock_trip(member: TripMember, session: DbSession, now: Now) -> TripDetailOut:
    """Restore write access on a locked trip."""
    detail = await trips.unlock_trip(session, member.trip_id, member.member_id, now)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TripDetailOut.model_validate(detail)
