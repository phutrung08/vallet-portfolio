from fastapi import APIRouter, HTTPException, status

from app.api.deps import ReadonlySnapshot, TripMember
from app.api.schemas.balances import BalancesOut, TripSpendSummaryOut
from app.services import balances, summary

router = APIRouter(prefix="/trips/{trip_id}", tags=["balances"])


@router.get("/balances")
async def get_balances(caller: TripMember, snapshot: ReadonlySnapshot) -> BalancesOut:
    """Compute member standings and suggested transfers under a consistent snapshot."""
    sheet = await balances.get_balances(snapshot, caller.trip_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return BalancesOut.model_validate(sheet)


@router.get("/summary")
async def get_trip_summary(caller: TripMember, snapshot: ReadonlySnapshot) -> TripSpendSummaryOut:
    """Return server-aggregated spend metrics, category percentages, and payer totals."""
    report = await summary.get_trip_summary(snapshot, caller.trip_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TripSpendSummaryOut.model_validate(report)
