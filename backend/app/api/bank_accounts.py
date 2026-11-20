from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AppSettings, DbSession, Now, TripMember
from app.api.schemas.bank_accounts import (
    BankAccountListOut,
    BankAccountOut,
    BankAccountRequest,
    BankListOut,
    BankOut,
)
from app.services import bank_accounts

router = APIRouter(tags=["bank accounts"])

_BANK_LIST = BankListOut(
    banks=[BankOut.model_validate(bank) for bank in bank_accounts.list_banks()]
)


@router.get("/banks")
async def list_banks(response: Response) -> BankListOut:
    """Return the static supported Vietnamese banks registry."""
    response.headers["Cache-Control"] = "public, max-age=86400"
    return _BANK_LIST


# "me" only: no route takes a member_id so members can only mutate their own bank account.
@router.put("/trips/{trip_id}/members/me/bank-account")
async def set_own_bank_account(
    body: BankAccountRequest,
    caller: TripMember,
    session: DbSession,
    settings: AppSettings,
    now: Now,
    response: Response,
) -> BankAccountOut:
    """Encrypt and store the caller's own bank account for receiving settlements."""
    saved = await bank_accounts.set_own_bank_account(
        session,
        settings.bank_data_key_bytes,
        caller.trip_id,
        caller.member_id,
        body.to_new_account(),
        now,
    )
    if saved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    response.headers["Cache-Control"] = "no-store"
    return BankAccountOut.model_validate(saved)


@router.delete("/trips/{trip_id}/members/me/bank-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_own_bank_account(caller: TripMember, session: DbSession, now: Now) -> None:
    """Remove the caller's stored bank account for this trip."""
    if not await bank_accounts.delete_own_bank_account(
        session, caller.trip_id, caller.member_id, now
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)


@router.get("/trips/{trip_id}/bank-accounts")
async def list_bank_accounts(
    caller: TripMember, session: DbSession, response: Response
) -> BankAccountListOut:
    """List masked bank account views for members of this trip without client caching."""
    listed = await bank_accounts.list_bank_accounts(session, caller.trip_id)
    response.headers["Cache-Control"] = "no-store"
    return BankAccountListOut(accounts=[BankAccountOut.model_validate(a) for a in listed])
