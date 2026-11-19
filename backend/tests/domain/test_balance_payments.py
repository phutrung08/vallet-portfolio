"""Settlement payments: cash handed from one member to another moves both nets."""

import random

import pytest

from app.domain.balance import BalanceError, Expense, MemberBalance, Payment, compute_balances
from app.domain.settle import Transfer, settle
from app.domain.split import MemberId, split_equal
from tests.domain.test_balance import ABC, nets, random_trip

# a paid 300 for a, b and c: b and c each owe a 100.
DINNER = [Expense(300, "a", split_equal(300, ABC))]


def test_a_payment_moves_both_nets_and_is_totalled() -> None:
    result = compute_balances(ABC, DINNER, payments=[Payment("b", "a", 40)])

    assert result["a"] == MemberBalance(
        paid=300, contributed=0, share=100, sent=0, received=40, net=160
    )
    assert result["b"] == MemberBalance(
        paid=0, contributed=0, share=100, sent=40, received=0, net=-60
    )
    assert nets(result) == {"a": 160, "b": -60, "c": -100}


def test_paying_one_suggested_transfer_removes_it() -> None:
    before = settle(nets(compute_balances(ABC, DINNER)))
    assert before == [Transfer("b", "a", 100), Transfer("c", "a", 100)]

    after = compute_balances(ABC, DINNER, payments=[Payment("b", "a", 100)])

    assert settle(nets(after)) == [Transfer("c", "a", 100)]


def test_paying_every_suggested_transfer_settles_everyone() -> None:
    transfers = settle(nets(compute_balances(ABC, DINNER)))
    payments = [Payment(t.payer, t.payee, t.amount) for t in transfers]

    result = compute_balances(ABC, DINNER, payments=payments)

    assert nets(result) == dict.fromkeys(ABC, 0)
    assert settle(nets(result)) == []


def test_a_partial_payment_leaves_a_smaller_transfer() -> None:
    result = compute_balances(ABC, DINNER, payments=[Payment("c", "a", 30)])

    assert settle(nets(result)) == [Transfer("b", "a", 100), Transfer("c", "a", 70)]


def test_an_overpayment_flips_the_sign() -> None:
    result = compute_balances(ABC, DINNER, payments=[Payment("b", "a", 150)])

    assert nets(result) == {"a": 50, "b": 50, "c": -100}
    assert settle(nets(result)) == [Transfer("c", "a", 50), Transfer("c", "b", 50)]


def test_a_payment_between_people_who_owe_nothing_creates_a_debt() -> None:
    result = compute_balances(ABC, [], payments=[Payment("b", "c", 25)])

    assert nets(result) == {"a": 0, "b": 25, "c": -25}


def test_payments_from_a_generator_are_iterated_once() -> None:
    payments = (Payment("b", "a", x) for x in (10, 20))
    assert nets(compute_balances(ABC, DINNER, payments=payments))["b"] == -70


@pytest.mark.parametrize(
    ("payment", "message"),
    [
        (Payment("b", "a", 0), "payment amount must be > 0, got 0"),
        (Payment("b", "a", -5), "payment amount must be > 0, got -5"),
        (Payment("b", "b", 10), "payment from 'b' to themselves"),
        (Payment("z", "a", 10), "payment payer 'z' is not a trip member"),
        (Payment("a", "z", 10), "payment payee 'z' is not a trip member"),
    ],
)
def test_rejects_invalid_payments(payment: Payment, message: str) -> None:
    with pytest.raises(BalanceError, match=message):
        compute_balances(ABC, DINNER, payments=[payment])


def _random_payments(rng: random.Random, members: list[MemberId]) -> list[Payment]:
    if len(members) < 2:
        return []
    payments = []
    for _ in range(rng.randint(0, 10)):
        payer, payee = rng.sample(members, 2)
        payments.append(Payment(payer, payee, rng.randint(1, 10**9)))
    return payments


def test_generated_trips_with_payments_balance_to_zero_and_settle() -> None:
    rng = random.Random(20261115)  # noqa: S311 -- deterministic test data, not security
    for _ in range(500):
        members, expenses, contributions = random_trip(rng)
        holder = rng.choice(members)
        payments = _random_payments(rng, members)
        result = compute_balances(members, expenses, contributions, holder, payments)
        without = compute_balances(members, expenses, contributions, holder)
        total = sum(p.amount for p in payments)
        assert sum(b.net for b in result.values()) == 0
        assert sum(b.sent for b in result.values()) == sum(b.received for b in result.values())
        assert sum(b.sent for b in result.values()) == total
        for member in members:
            moved = result[member].sent - result[member].received
            assert result[member].net == without[member].net + moved
        after = nets(result)
        for transfer in settle(after):
            after[transfer.payer] += transfer.amount
            after[transfer.payee] -= transfer.amount
        assert all(value == 0 for value in after.values())
