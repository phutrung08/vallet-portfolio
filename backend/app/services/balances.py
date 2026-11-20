"""Member balances and minimal settlement transfers computed from trip records."""

import logging
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import balance
from app.domain.settle import SettleError, settle
from app.repositories import expenses as expense_repository
from app.repositories import fund as fund_repository
from app.repositories import payments as payment_repository
from app.repositories import trips as trip_repository
from app.repositories.models import Member, Payment, Trip
from app.services.errors import InconsistentTripData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FundBalance:
    """Current shared fund custodian and remaining cash balance."""

    holder_id: uuid.UUID | None
    remaining: int


@dataclass(frozen=True)
class MemberStanding:
    """Financial summary for one trip member (paid, contributed, share, settled, net)."""

    member_id: uuid.UUID
    paid: int
    contributed: int
    share: int
    sent: int
    received: int
    net: int
    removed: bool


@dataclass(frozen=True)
class TransferView:
    """Suggested settlement transfer from debtor to creditor."""

    payer: uuid.UUID
    payee: uuid.UUID
    amount: int


@dataclass(frozen=True)
class BalanceSheet:
    """Complete trip balance sheet and minimum-transfer settlement plan."""

    currency: str
    fund: FundBalance
    members: Sequence[MemberStanding]
    transfers: Sequence[TransferView]


def _domain_expenses(
    rows: Sequence[tuple[uuid.UUID, uuid.UUID | None, int, uuid.UUID, int]],
) -> list[balance.Expense]:
    """Group per-share rows back into domain expenses keyed by stringified UUIDs."""
    shares: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    heads: dict[uuid.UUID, tuple[uuid.UUID | None, int]] = {}
    for expense_id, payer, amount, member_id, part in rows:
        heads[expense_id] = (payer, amount)
        shares[expense_id][str(member_id)] = part
    return [
        balance.Expense(amount, None if payer is None else str(payer), shares[expense_id])
        for expense_id, (payer, amount) in heads.items()
    ]


def _domain_payments(rows: Sequence[Payment]) -> list[balance.Payment]:
    return [balance.Payment(str(p.payer_id), str(p.payee_id), p.amount) for p in rows]


def _standing(member: Member, totals: balance.MemberBalance) -> MemberStanding:
    return MemberStanding(
        member_id=member.id,
        paid=totals.paid,
        contributed=totals.contributed,
        share=totals.share,
        sent=totals.sent,
        received=totals.received,
        net=totals.net,
        removed=member.removed_at is not None,
    )


def _compute(
    trip: Trip,
    members: Sequence[Member],
    expenses: Sequence[balance.Expense],
    contributions: dict[str, int],
    payments: Sequence[balance.Payment],
) -> BalanceSheet:
    """Compute member standings across all members (active and removed) to preserve zero-sum."""
    holder = None if trip.fund_holder_id is None else str(trip.fund_holder_id)
    try:
        balances = balance.compute_balances(
            [str(m.id) for m in members], expenses, contributions, holder, payments
        )
        transfers = settle({member: b.net for member, b in balances.items()})
    except (balance.BalanceError, SettleError):
        # Never log domain messages: they include member UUIDs.
        logger.error("Stored trip data is inconsistent; balances cannot be computed")
        raise InconsistentTripData from None
    return BalanceSheet(
        currency=trip.currency,
        fund=FundBalance(trip.fund_holder_id, balance.fund_remaining(expenses, contributions)),
        members=[_standing(m, balances[str(m.id)]) for m in members],
        transfers=[
            TransferView(uuid.UUID(t.payer), uuid.UUID(t.payee), t.amount) for t in transfers
        ],
    )


async def get_balances(session: AsyncSession, trip_id: uuid.UUID) -> BalanceSheet | None:
    """Compute balances in four constant queries: trip+members, shares, contributions, payments."""
    found = await trip_repository.find_trip_with_members(session, trip_id)
    if found is None:
        return None
    trip, members = found
    rows = await expense_repository.live_share_rows(session, trip_id)
    live = await fund_repository.list_live_contributions(session, trip_id)
    contributions: dict[str, int] = defaultdict(int)
    for contribution in live:
        contributions[str(contribution.member_id)] += contribution.amount
    payments = await payment_repository.list_live_payments(session, trip_id)
    return _compute(
        trip, members, _domain_expenses(rows), contributions, _domain_payments(payments)
    )
