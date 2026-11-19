"""Turn net balances into a short list of transfers that settles everyone."""

import heapq
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.split import MemberId


@dataclass(frozen=True, slots=True)
class Transfer:
    """``payer`` sends ``amount`` (> 0, minor units) to ``payee``."""

    payer: MemberId
    payee: MemberId
    amount: int


class SettleError(ValueError):
    """Raised when net balances cannot be settled."""


def settle(nets: Mapping[MemberId, int]) -> list[Transfer]:
    """Return transfers that bring every net (> 0 receives, < 0 pays) to exactly 0.

    Greedy heuristic: repeatedly the member who owes the most pays the member
    who is owed the most ``min`` of the two amounts. Each transfer clears at
    least one of them, so there are at most ``k - 1`` transfers for ``k``
    non-zero members, and nobody both pays and receives. This is not guaranteed
    to be the true minimum number of transfers (an NP-hard problem in general).
    Ties are broken by the mapping's iteration order, so the result is
    deterministic. The nets must sum to 0.
    """
    total = sum(nets.values())
    if total != 0:
        raise SettleError(f"nets must sum to 0, got {total}")
    order = {member: index for index, member in enumerate(nets)}
    creditors = [(-net, order[m], m) for m, net in nets.items() if net > 0]
    debtors = [(net, order[m], m) for m, net in nets.items() if net < 0]
    heapq.heapify(creditors)
    heapq.heapify(debtors)

    transfers: list[Transfer] = []
    while creditors:
        owed, payee_index, payee = heapq.heappop(creditors)
        owes, payer_index, payer = heapq.heappop(debtors)
        amount = min(-owed, -owes)
        transfers.append(Transfer(payer, payee, amount))
        if -owed > amount:
            heapq.heappush(creditors, (owed + amount, payee_index, payee))
        if -owes > amount:
            heapq.heappush(debtors, (owes + amount, payer_index, payer))
    return transfers
