"""Settlement payments recorded between trip members to clear balances."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.repositories import payments as repository
from app.repositories import trips as trip_repository
from app.repositories.models import Payment
from app.services.errors import RuleViolation
from app.services.expenses import require_capacity
from app.services.trip_guards import lock_trip_for_actor, require_unlocked_trip


@dataclass(frozen=True)
class NewPayment:
    """Validated settlement payment creation input."""

    payer: uuid.UUID
    payee: uuid.UUID
    amount: int
    paid_on: date
    note: str | None


@dataclass(frozen=True)
class PaymentView:
    """Serialized settlement payment record."""

    id: uuid.UUID
    payer: uuid.UUID
    payee: uuid.UUID
    amount: int
    paid_on: date
    note: str | None
    created_by: uuid.UUID
    created_at: datetime


def _payment_view(payment: Payment) -> PaymentView:
    return PaymentView(
        id=payment.id,
        payer=payment.payer_id,
        payee=payment.payee_id,
        amount=payment.amount,
        paid_on=payment.paid_on,
        note=payment.note,
        created_by=payment.created_by_id,
        created_at=payment.created_at,
    )


async def list_payments(session: AsyncSession, trip_id: uuid.UUID) -> list[PaymentView]:
    """List live settlement payments newest first."""
    return [_payment_view(p) for p in await repository.list_live_payments(session, trip_id)]


async def record_payment(
    session: AsyncSession,
    trip_id: uuid.UUID,
    author_id: uuid.UUID,
    data: NewPayment,
    now: datetime,
) -> PaymentView | None:
    """Record a settlement payment on an unlocked trip, or return None when absent.

    Closed trips still accept settlement payments. Both active and soft-removed trip members may
    act as payer or payee so outstanding debts can still be settled after leaving.
    """
    # Exclusive lock prevents concurrent creates from bypassing MAX_LIVE_PAYMENTS.
    trip = await lock_trip_for_actor(
        session, trip_id, author_id, require_open=False, exclusive=True
    )
    if trip is None:
        return None
    require_unlocked_trip(trip)
    live = await repository.count_live_payments(session, trip_id)
    require_capacity(live, limits.MAX_LIVE_PAYMENTS)
    members = await trip_repository.list_members(session, trip_id)
    if not {data.payer, data.payee} <= {m.id for m in members}:
        raise RuleViolation("member_not_active")
    payment = Payment(
        id=uuid.uuid4(),
        trip_id=trip_id,
        payer_id=data.payer,
        payee_id=data.payee,
        amount=data.amount,
        paid_on=data.paid_on,
        note=data.note,
        created_by_id=author_id,
        created_at=now,
    )
    repository.add_payment(session, payment)
    return _payment_view(payment)


async def delete_payment(
    session: AsyncSession,
    trip_id: uuid.UUID,
    payment_id: uuid.UUID,
    editor_id: uuid.UUID,
    now: datetime,
) -> bool:
    """Soft-delete a live payment on an unlocked trip after post-lock active-caller validation."""
    trip = await lock_trip_for_actor(
        session, trip_id, editor_id, require_open=False, exclusive=False
    )
    if trip is None:
        return False
    require_unlocked_trip(trip)
    payment = await repository.lock_live_payment(session, trip_id, payment_id)
    if payment is None:
        return False
    payment.deleted_at = now
    return True
