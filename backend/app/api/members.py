from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Now, TripMember
from app.api.schemas.members import MemberNameRequest
from app.api.schemas.trips import MemberOut
from app.services import members

router = APIRouter(prefix="/trips/{trip_id}", tags=["members"])


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    body: MemberNameRequest, caller: TripMember, session: DbSession, now: Now
) -> MemberOut:
    """Add a new active member to the trip."""
    added = await members.add_member(
        session, caller.trip_id, caller.member_id, body.display_name, now
    )
    if added is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return MemberOut.model_validate(added)


@router.patch("/members/{member_id}")
async def rename_member(
    member_id: UUID, body: MemberNameRequest, caller: TripMember, session: DbSession, now: Now
) -> MemberOut:
    """Rename an active member of the trip."""
    renamed = await members.rename_member(
        session, caller.trip_id, caller.member_id, member_id, body.display_name, now
    )
    if renamed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return MemberOut.model_validate(renamed)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(member_id: UUID, caller: TripMember, session: DbSession, now: Now) -> None:
    """Soft-remove a member and revoke their device sessions."""
    if not await members.remove_member(session, caller.trip_id, caller.member_id, member_id, now):
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@router.post("/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_trip(caller: TripMember, session: DbSession, now: Now) -> None:
    """Detach the current device from this trip without removing the member."""
    await members.leave_trip(session, caller.device_id, caller.trip_id, caller.member_id, now)
