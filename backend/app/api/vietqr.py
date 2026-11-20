from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import AppSettings, DbSession, TripMember
from app.api.schemas.vietqr import VietQrOut
from app.services import vietqr

router = APIRouter(prefix="/trips/{trip_id}", tags=["vietqr"])


@router.get("/vietqr")
async def get_transfer_qr(
    payee: UUID,
    amount: Annotated[int, Query(ge=1, le=vietqr.MAX_QR_AMOUNT)],
    caller: TripMember,
    session: DbSession,
    settings: AppSettings,
    response: Response,
) -> VietQrOut:
    """Decrypt ``payee``'s bank account in-memory to render an uncached VietQR transfer payload."""
    qr = await vietqr.transfer_qr(
        session, settings.bank_data_key_bytes, caller.trip_id, payee, amount
    )
    if qr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    response.headers["Cache-Control"] = "no-store"
    return VietQrOut.model_validate(qr)
