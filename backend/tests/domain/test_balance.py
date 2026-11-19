import random
from collections.abc import Mapping

import pytest

from app.domain.balance import (
    BalanceError,
    Expense,
    MemberBalance,
    compute_balances,
    fund_remaining,
)
from app.domain.split import MemberId, split_equal

ABC = ["a", "b", "c"]
TUV = ["t", "u", "v"]


def nets(balances: Mapping[MemberId, MemberBalance]) -> dict[MemberId, int]:
    return {member: balance.net for member, balance in balances.items()}


def test_no_fund_simple() -> None:
    expense = Expense(300, "a", split_equal(300, ABC))
    result = compute_balances(ABC, [expense])
    assert list(result) == ABC
    assert result["a"] == MemberBalance(
        paid=300, contributed=0, share=100, sent=0, received=0, net=200
    )
    assert nets(result) == {"a": 200, "b": -100, "c": -100}
    assert sum(nets(result).values()) == 0


def test_member_absent_from_expense_has_no_share() -> None:
    expense = Expense(200, "a", {"a": 100, "b": 100})
    result = compute_balances(ABC, [expense])
    assert result["c"] == MemberBalance(paid=0, contributed=0, share=0, sent=0, received=0, net=0)
    assert nets(result) == {"a": 100, "b": -100, "c": 0}


def test_expense_paid_only_for_oneself_changes_no_net() -> None:
    shared = Expense(300, "a", split_equal(300, ABC))
    personal = Expense(450, "b", {"b": 450})
    assert nets(compute_balances(ABC, [shared, personal])) == nets(compute_balances(ABC, [shared]))


def test_fund_holder_returns_what_is_left() -> None:
    contributions = dict.fromkeys(TUV, 1_000)
    expenses = [Expense(600, None, split_equal(600, TUV))]
    assert fund_remaining(expenses, contributions) == 2_400
    result = compute_balances(TUV, expenses, contributions, fund_holder="t")
    assert nets(result) == {"t": -1_600, "u": 800, "v": 800}
    assert result["t"] == MemberBalance(
        paid=0, contributed=1_000, share=200, sent=0, received=0, net=-1_600
    )


def test_fund_with_out_of_pocket_advance_by_non_holder() -> None:
    contributions = dict.fromkeys(TUV, 1_000)
    expenses = [
        Expense(900, None, split_equal(900, TUV)),
        Expense(600, "u", split_equal(600, TUV)),
    ]
    assert fund_remaining(expenses, contributions) == 2_100
    result = compute_balances(TUV, expenses, contributions, fund_holder="t")
    assert nets(result) == {"t": -1_600, "u": 1_100, "v": 500}
    assert sum(nets(result).values()) == 0


def test_overdrawn_fund_means_holder_is_owed() -> None:
    contributions = dict.fromkeys(TUV, 100)
    expenses = [Expense(500, None, {"t": 200, "u": 150, "v": 150})]
    assert fund_remaining(expenses, contributions) == -200
    result = compute_balances(TUV, expenses, contributions, fund_holder="t")
    assert nets(result) == {"t": 100, "u": -50, "v": -50}


def test_member_without_contribution() -> None:
    contributions = {"t": 500, "u": 500}
    expenses = [Expense(600, None, split_equal(600, TUV))]
    result = compute_balances(TUV, expenses, contributions, fund_holder="t")
    assert result["v"] == MemberBalance(
        paid=0, contributed=0, share=200, sent=0, received=0, net=-200
    )
    assert nets(result) == {"t": -100, "u": 300, "v": -200}


def test_generator_expenses_are_iterated_once() -> None:
    amounts = [300, 600, 900]
    result = compute_balances(ABC, (Expense(x, "a", split_equal(x, ABC)) for x in amounts))
    assert nets(result) == {"a": 1_200, "b": -600, "c": -600}


def test_zero_fund_expense_needs_no_holder() -> None:
    result = compute_balances(ABC, [Expense(0, None, dict.fromkeys(ABC, 0))], {"a": 0})
    assert nets(result) == dict.fromkeys(ABC, 0)


@pytest.mark.parametrize(
    ("members", "expenses", "contributions", "fund_holder", "message"),
    [
        ([], [], None, None, "members must not be empty"),
        (["a", "b", "a"], [], None, None, r"duplicate members: \['a'\]"),
        (ABC, [Expense(-1, "a", {"a": -1})], None, None, "expense amount must be >= 0"),
        (ABC, [Expense(100, "a", {"a": 60, "b": 30})], None, None, "shares sum to 90"),
        (ABC, [Expense(0, "a", {"a": 10, "b": -10})], None, None, "share of 'b' must be >= 0"),
        (ABC, [Expense(100, "z", {"a": 100})], None, None, "payer 'z' is not a trip member"),
        (ABC, [Expense(100, "a", {"z": 100})], None, None, "share holder 'z' is not"),
        (ABC, [], {"z": 100}, "a", "contributor 'z' is not a trip member"),
        (ABC, [], {"a": -5}, "a", "contribution of 'a' must be >= 0"),
        (ABC, [], {"a": 100}, None, "a fund holder is required"),
        (ABC, [Expense(100, None, {"a": 100})], None, None, "a fund holder is required"),
        (ABC, [], {"a": 100}, "z", "fund holder 'z' is not a trip member"),
    ],
)
def test_rejects_invalid_input(
    members: list[MemberId],
    expenses: list[Expense],
    contributions: dict[MemberId, int] | None,
    fund_holder: MemberId | None,
    message: str,
) -> None:
    with pytest.raises(BalanceError, match=message):
        compute_balances(members, expenses, contributions, fund_holder)
    assert issubclass(BalanceError, ValueError)


def random_trip(rng: random.Random) -> tuple[list[MemberId], list[Expense], dict[MemberId, int]]:
    members = [f"m{i}" for i in range(rng.randint(1, 8))]
    expenses = []
    for _ in range(rng.randint(0, 20)):
        amount = rng.randint(0, 10**9)
        participants = rng.sample(members, rng.randint(1, len(members)))
        paid_by = rng.choice([None, *members])
        expenses.append(Expense(amount, paid_by, split_equal(amount, participants)))
    contributions = {m: rng.randint(0, 10**9) for m in members if rng.random() < 0.7}
    return members, expenses, contributions


def test_generated_trips_balance_to_zero() -> None:
    rng = random.Random(20261114)  # noqa: S311 -- deterministic test data, not security
    for _ in range(500):
        members, expenses, contributions = random_trip(rng)
        holder = rng.choice(members)
        result = compute_balances(members, expenses, contributions, holder)
        fund_paid = sum(e.amount for e in expenses if e.paid_by is None)
        assert list(result) == members
        assert sum(b.net for b in result.values()) == 0
        assert sum(b.paid for b in result.values()) + fund_paid == sum(
            b.share for b in result.values()
        )
