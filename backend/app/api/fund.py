from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Now, ReadonlySnapshot, TripMember
from app.api.idempotency import IdempotentCreate
from app.api.schemas.fund import ContributionOut, ContributionRequest, FundOut, HolderRequest
from app.services import fund

router = APIRouter(prefix="/trips/{trip_id}/fund", tags=["fund"])


@router.get("")
async def get_fund(caller: TripMember, snapshot: ReadonlySnapshot) -> FundOut:
    """Return a snapshot-consistent shared fund overview for the trip."""
    summary = await fund.get_summary(snapshot, caller.trip_id)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return FundOut.model_validate(summary)


@router.put("")
async def set_fund_holder(
    body: HolderRequest, caller: TripMember, session: DbSession, now: Now
) -> FundOut:
    """Enable, disable, or reassign the shared fund holder."""
    summary = await fund.set_holder(session, caller.trip_id, caller.member_id, body.holder_id, now)
    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return FundOut.model_validate(summary)


@router.post("/contributions", status_code=status.HTTP_201_CREATED)
async def add_contribution(
    body: ContributionRequest,
    caller: TripMember,
    session: DbSession,
    now: Now,
    once: IdempotentCreate,
) -> ContributionOut:
    """Record a member contribution into the trip's shared fund."""

    async def write() -> ContributionOut:
        added = await fund.add_contribution(
            session,
            caller.trip_id,
            caller.member_id,
            body.member_id,
            body.amount,
            body.contributed_on,
            now,
        )
        if added is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return ContributionOut.model_validate(added)

    return await once.run(body, ContributionOut, write)


@router.delete("/contributions/{contribution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contribution(
    contribution_id: UUID, caller: TripMember, session: DbSession, now: Now
) -> None:
    """Soft-delete a live shared fund contribution."""
    if not await fund.delete_contribution(
        session, caller.trip_id, caller.member_id, contribution_id, now
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
