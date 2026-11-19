import random
from collections.abc import Mapping

import pytest

from app.domain.settle import SettleError, Transfer, settle
from app.domain.split import MemberId

GROUP_TRIP_NETS = {
    "an": -2_386_183,
    "binh": 3_694_817,
    "chi": -2_622_683,
    "dung": 1_518_567,
    "em": 2_409_917,
    "giang": -2_614_435,
}


def assert_settles(nets: Mapping[MemberId, int], transfers: list[Transfer]) -> None:
    remaining = dict(nets)
    for transfer in transfers:
        assert transfer.amount > 0
        assert transfer.payer != transfer.payee
        remaining[transfer.payer] += transfer.amount
        remaining[transfer.payee] -= transfer.amount
    assert all(value == 0 for value in remaining.values())
    payers = {t.payer for t in transfers}
    payees = {t.payee for t in transfers}
    assert not payers & payees
    non_zero = sum(1 for net in nets.values() if net != 0)
    assert len(transfers) <= max(non_zero - 1, 0)


def test_simple() -> None:
    nets = {"a": 200, "b": -100, "c": -100}
    transfers = settle(nets)
    assert transfers == [Transfer("b", "a", 100), Transfer("c", "a", 100)]
    assert_settles(nets, transfers)


@pytest.mark.parametrize("nets", [{}, {"a": 0, "b": 0, "c": 0}])
def test_nothing_to_settle(nets: dict[MemberId, int]) -> None:
    assert settle(nets) == []
    assert_settles(nets, [])


def test_one_debtor_several_creditors() -> None:
    nets = {"a": 50, "b": -600, "c": 300, "d": 250}
    transfers = settle(nets)
    assert transfers == [
        Transfer("b", "c", 300),
        Transfer("b", "d", 250),
        Transfer("b", "a", 50),
    ]
    assert_settles(nets, transfers)


def test_several_debtors_one_creditor() -> None:
    nets = {"a": -50, "b": -300, "c": 600, "d": -250}
    transfers = settle(nets)
    assert transfers == [
        Transfer("b", "c", 300),
        Transfer("d", "c", 250),
        Transfer("a", "c", 50),
    ]
    assert_settles(nets, transfers)


def test_real_trip_nets() -> None:
    transfers = settle(GROUP_TRIP_NETS)
    assert_settles(GROUP_TRIP_NETS, transfers)
    assert len(transfers) <= 5
    owed = sum(net for net in GROUP_TRIP_NETS.values() if net > 0)
    assert sum(t.amount for t in transfers) == owed


def test_non_zero_sum_is_rejected() -> None:
    with pytest.raises(SettleError, match="nets must sum to 0, got 1"):
        settle({**GROUP_TRIP_NETS, "giang": -2_614_434})
    assert issubclass(SettleError, ValueError)


def test_ties_follow_mapping_order() -> None:
    nets = {"a": -100, "b": -100, "c": 100, "d": 100}
    assert settle(nets) == [Transfer("a", "c", 100), Transfer("b", "d", 100)]
    reordered = {"b": -100, "a": -100, "d": 100, "c": 100}
    assert settle(reordered) == [Transfer("b", "d", 100), Transfer("a", "c", 100)]
    assert settle(nets) == settle(dict(nets))


def _random_nets(rng: random.Random) -> dict[MemberId, int]:
    """Zero-sum nets built by moving random amounts between pairs, each |net| <= 10**10."""
    members = [f"m{i}" for i in range(rng.randint(1, 30))]
    nets = dict.fromkeys(members, 0)
    for _ in range(rng.randint(0, 60) if len(members) > 1 else 0):
        payer, payee = rng.sample(members, 2)
        amount = rng.randint(1, 10**10)
        if nets[payer] - amount >= -(10**10) and nets[payee] + amount <= 10**10:
            nets[payer] -= amount
            nets[payee] += amount
    return nets


def test_generated_nets_settle() -> None:
    rng = random.Random(20261114)  # noqa: S311 -- deterministic test data, not security
    for _ in range(500):
        nets = _random_nets(rng)
        transfers = settle(nets)
        assert_settles(nets, transfers)
        assert transfers == settle(nets)
