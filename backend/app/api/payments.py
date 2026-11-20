from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, Now, TripMember
from app.api.idempotency import IdempotentCreate
from app.api.schemas.payments import PaymentListOut, PaymentOut, PaymentRequest
from app.services import payments

router = APIRouter(prefix="/trips/{trip_id}/payments", tags=["payments"])


@router.get("")
async def list_payments(caller: TripMember, session: DbSession) -> PaymentListOut:
    """List live settlement payments recorded for the trip."""
    listed = await payments.list_payments(session, caller.trip_id)
    return PaymentListOut(payments=[PaymentOut.model_validate(p) for p in listed])


@router.post("", status_code=status.HTTP_201_CREATED)
async def record_payment(
    body: PaymentRequest, caller: TripMember, session: DbSession, now: Now, once: IdempotentCreate
) -> PaymentOut:
    """Record a settlement payment between two trip members with optional idempotency."""

    async def write() -> PaymentOut:
        recorded = await payments.record_payment(
            session, caller.trip_id, caller.member_id, body.to_new_payment(), now
        )
        if recorded is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return PaymentOut.model_validate(recorded)

    return await once.run(body, PaymentOut, write)


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: UUID, caller: TripMember, session: DbSession, now: Now
) -> None:
    """Soft-delete a live settlement payment."""
    deleted = await payments.delete_payment(
        session, caller.trip_id, payment_id, caller.member_id, now
    )
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
