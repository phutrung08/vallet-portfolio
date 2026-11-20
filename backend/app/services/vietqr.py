"""VietQR EMVCo payload generation for settling transfers to a payee's encrypted account."""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import DecryptionError, decrypt
from app.domain.vietqr import MAX_AMOUNT, VietQrError, build_transfer_payload, transfer_message
from app.repositories import bank_accounts as bank_repository
from app.repositories import trips as trip_repository
from app.services.bank_accounts import bank_account_aad, bank_short_name
from app.services.errors import InconsistentTripData, RuleViolation

logger = logging.getLogger(__name__)

MAX_QR_AMOUNT = MAX_AMOUNT
MESSAGE_PREFIX = "VL "


@dataclass(frozen=True)
class TransferQr:
    """VietQR transfer payload plus masked beneficiary metadata for confirmation display."""

    # Keeps plaintext account number inside payload out of reprs and exception logs.
    payload: str = field(repr=False)
    bank_bin: str
    bank_short_name: str
    account_name: str
    account_last4: str
    amount: int
    message: str


async def transfer_qr(
    session: AsyncSession, key: bytes, trip_id: uuid.UUID, payee_id: uuid.UUID, amount: int
) -> TransferQr | None:
    """Build a VietQR payload for ``payee_id``, or return None when the trip does not exist."""
    trip = await trip_repository.find_trip(session, trip_id)
    if trip is None:
        return None
    if trip.currency != "VND":
        raise RuleViolation("currency_not_supported")
    if await trip_repository.find_member(session, trip_id, payee_id) is None:
        raise RuleViolation("member_not_active")
    account = await bank_repository.find_bank_account(session, trip_id, payee_id)
    if account is None:
        raise RuleViolation("no_bank_account")
    message = transfer_message(MESSAGE_PREFIX + trip.name)
    try:
        number = decrypt(key, account.account_number_encrypted, bank_account_aad(trip_id, payee_id))
        payload = build_transfer_payload(account.bank_bin, number, amount, message)
    except (DecryptionError, VietQrError):
        # Never log ciphertexts, keys, or account metadata.
        logger.error("A stored bank account cannot be turned into a VietQR payload")
        raise InconsistentTripData from None
    return TransferQr(
        payload=payload,
        bank_bin=account.bank_bin,
        bank_short_name=bank_short_name(account.bank_bin),
        account_name=account.account_name,
        account_last4=account.account_last4,
        amount=amount,
        message=message,
    )
