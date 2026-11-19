"""Per-member balances of a trip: what each advanced, contributed, owes and has paid back."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.domain.split import MemberId


@dataclass(frozen=True, slots=True)
class Expense:
    """An expense and its per-member split; ``paid_by`` None means paid from the fund."""

    amount: int
    paid_by: MemberId | None
    shares: Mapping[MemberId, int]


@dataclass(frozen=True, slots=True)
class Payment:
    """A settlement: ``payer`` handed ``payee`` ``amount`` (> 0) outside any expense."""

    payer: MemberId
    payee: MemberId
    amount: int


@dataclass(frozen=True, slots=True)
class MemberBalance:
    """A member's totals; ``net > 0`` should receive money, ``net < 0`` should pay.

    ``sent`` and ``received`` are the member's settlement payments out and in.
    """

    paid: int
    contributed: int
    share: int
    sent: int
    received: int
    net: int


class BalanceError(ValueError):
    """Raised when balances cannot be computed from the given trip data."""


def fund_remaining(expenses: Iterable[Expense], contributions: Mapping[MemberId, int]) -> int:
    """Contributions minus fund-paid expenses. Negative means the fund is overdrawn."""
    spent = sum(expense.amount for expense in expenses if expense.paid_by is None)
    return sum(contributions.values()) - spent


def _require_members(members: Sequence[MemberId]) -> frozenset[MemberId]:
    if not members:
        raise BalanceError("members must not be empty")
    known = frozenset(members)
    if len(known) != len(members):
        duplicates = sorted({m for m in members if members.count(m) > 1})
        raise BalanceError(f"duplicate members: {duplicates}")
    return known


def _require_known(member: MemberId, known: frozenset[MemberId], role: str) -> None:
    if member not in known:
        raise BalanceError(f"{role} {member!r} is not a trip member")


def _validate_expense(expense: Expense, known: frozenset[MemberId]) -> None:
    """An expense is valid when its amount and shares are >= 0 and the shares sum to it."""
    if expense.amount < 0:
        raise BalanceError(f"expense amount must be >= 0, got {expense.amount}")
    if expense.paid_by is not None:
        _require_known(expense.paid_by, known, "payer")
    for member, share in expense.shares.items():
        _require_known(member, known, "share holder")
        if share < 0:
            raise BalanceError(f"share of {member!r} must be >= 0, got {share}")
    shares_sum = sum(expense.shares.values())
    if shares_sum != expense.amount:
        raise BalanceError(f"shares sum to {shares_sum} but expense amount is {expense.amount}")


def _validate_contributions(
    contributions: Mapping[MemberId, int], known: frozenset[MemberId]
) -> None:
    for member, amount in contributions.items():
        _require_known(member, known, "contributor")
        if amount < 0:
            raise BalanceError(f"contribution of {member!r} must be >= 0, got {amount}")


def _validate_fund_holder(
    fund_holder: MemberId | None, known: frozenset[MemberId], has_fund_activity: bool
) -> None:
    if fund_holder is not None:
        _require_known(fund_holder, known, "fund holder")
    elif has_fund_activity:
        raise BalanceError("the trip has fund activity, so a fund holder is required")


def _validate_payment(payment: Payment, known: frozenset[MemberId]) -> None:
    if payment.amount <= 0:
        raise BalanceError(f"payment amount must be > 0, got {payment.amount}")
    if payment.payer == payment.payee:
        raise BalanceError(f"payment from {payment.payer!r} to themselves")
    _require_known(payment.payer, known, "payment payer")
    _require_known(payment.payee, known, "payment payee")


def _payment_totals(
    members: Sequence[MemberId], payments: Sequence[Payment]
) -> tuple[dict[MemberId, int], dict[MemberId, int]]:
    """Per member: total sent and total received in settlement payments."""
    sent = dict.fromkeys(members, 0)
    received = dict.fromkeys(members, 0)
    for payment in payments:
        sent[payment.payer] += payment.amount
        received[payment.payee] += payment.amount
    return sent, received


def _paid_and_share_totals(
    members: Sequence[MemberId], expenses: Sequence[Expense]
) -> tuple[dict[MemberId, int], dict[MemberId, int]]:
    """Per member: total advanced out of pocket, and total of their shares."""
    paid = dict.fromkeys(members, 0)
    share = dict.fromkeys(members, 0)
    for expense in expenses:
        if expense.paid_by is not None:
            paid[expense.paid_by] += expense.amount
        for member, amount in expense.shares.items():
            share[member] += amount
    return paid, share


def _validate(
    known: frozenset[MemberId],
    expenses: Sequence[Expense],
    contributions: Mapping[MemberId, int],
    fund_holder: MemberId | None,
    payments: Sequence[Payment],
) -> None:
    for expense in expenses:
        _validate_expense(expense, known)
    _validate_contributions(contributions, known)
    has_fund_activity = any(contributions.values()) or any(
        e.amount > 0 for e in expenses if e.paid_by is None
    )
    _validate_fund_holder(fund_holder, known, has_fund_activity)
    for payment in payments:
        _validate_payment(payment, known)


def compute_balances(
    members: Sequence[MemberId],
    expenses: Iterable[Expense],
    contributions: Mapping[MemberId, int] | None = None,
    fund_holder: MemberId | None = None,
    payments: Iterable[Payment] = (),
) -> dict[MemberId, MemberBalance]:
    """Compute each member's balance; keys follow ``members`` and the nets sum to 0.

    ``net = paid + contributed - share + sent - received``. A payment from P to Q
    moves cash from P to Q, so P is owed that much more and Q that much less; it
    cancels out across the two, so the nets still sum to 0. The fund holder
    physically holds the fund cash, so their net also subtracts ``fund_remaining``:
    they hand back what is left, or are owed the gap when the fund is overdrawn.
    """
    known = _require_members(members)
    all_expenses = tuple(expenses)
    all_payments = tuple(payments)
    fund = contributions or {}
    _validate(known, all_expenses, fund, fund_holder, all_payments)

    remaining = fund_remaining(all_expenses, fund)
    paid, share = _paid_and_share_totals(members, all_expenses)
    sent, received = _payment_totals(members, all_payments)
    balances: dict[MemberId, MemberBalance] = {}
    for member in members:
        contributed = fund.get(member, 0)
        net = paid[member] + contributed - share[member] + sent[member] - received[member]
        if member == fund_holder:
            net -= remaining
        balances[member] = MemberBalance(
            paid[member], contributed, share[member], sent[member], received[member], net
        )
    return balances
