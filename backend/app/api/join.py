"""The share link exchange. The token arrives only in POST bodies, never in a URL or a log."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import DbSession, Now, OptionalDeviceId, ensure_device
from app.api.schemas.join import JoinPreviewOut, JoinPreviewRequest, JoinRequest
from app.api.schemas.trips import TripDetailOut
from app.services import join

router = APIRouter(prefix="/join", tags=["join"])


@router.post("/preview")
async def preview_join(
    body: JoinPreviewRequest,
    session: DbSession,
    device_id: OptionalDeviceId,
    now: Now,
    response: Response,
) -> JoinPreviewOut:
    """Inspect a trip's public details and active member claim flags from a share token."""
    preview = await join.preview_trip(session, body.token, device_id, now)
    if preview is None:
        raise HTTPException(status_code=404)
    response.headers["Cache-Control"] = "no-store"
    return JoinPreviewOut.model_validate(preview)


@router.post("")
async def join_trip(
    body: JoinRequest,
    session: DbSession,
    device_id: Annotated[UUID, Depends(ensure_device)],
    response: Response,
    now: Now,
) -> TripDetailOut:
    """Attach the caller's device to an existing unjoined member or create a new member."""
    detail = await join.join_trip(session, device_id, body.token, body.choice, now)
    if detail is None:
        raise HTTPException(status_code=404)
    response.headers["Cache-Control"] = "no-store"
    return TripDetailOut.model_validate(detail)
