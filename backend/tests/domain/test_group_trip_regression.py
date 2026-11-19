"""Regression test on an anonymized 6-person group trip dataset (42 expenses, VND).

The reference spreadsheet rounded every row, so its totals differ from the exact integer results
by a few dong. The pinned values below are the exact results; change them only intentionally.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.balance import Expense, MemberBalance, compute_balances
from app.domain.settle import Transfer, settle
from app.domain.split import split_equal, split_exact

FIXTURE = Path(__file__).parent.parent / "fixtures" / "group_trip.json"
TOLERANCE = 3  # dong

# member: (paid, share, net)
PINNED: dict[str, tuple[int, int, int]] = {
    "an": (2_200_000, 4_586_184, -2_386_184),
    "binh": (8_565_000, 4_870_184, 3_694_816),
    "chi": (2_350_000, 4_972_684, -2_622_684),
    "dung": (6_605_000, 5_086_434, 1_518_566),
    "em": (6_694_000, 4_284_082, 2_409_918),
    "giang": (2_200_000, 4_814_432, -2_614_432),
}
PINNED_TRANSFERS = [
    Transfer("chi", "binh", 2_622_684),
    Transfer("giang", "em", 2_409_918),
    Transfer("an", "dung", 1_518_566),
    Transfer("an", "binh", 867_618),
    Transfer("giang", "binh", 204_514),
]
MEMBERS = list(PINNED)


def _shares(split: dict[str, Any], amount: int) -> dict[str, int]:
    match split["mode"]:
        case "equal":
            return split_equal(amount, split["participants"])
        case "exact":
            return split_exact(amount, split["amounts"])
        case mode:
            raise ValueError(f"unknown split mode: {mode!r}")


def _load() -> tuple[dict[str, Any], list[Expense]]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expenses = [
        Expense(e["amount"], e["paid_by"], _shares(e["split"], e["amount"]))
        for e in data["expenses"]
    ]
    return data, expenses


@pytest.fixture(scope="module")
def fixture_data() -> dict[str, Any]:
    return _load()[0]


@pytest.fixture(scope="module")
def expenses() -> list[Expense]:
    return _load()[1]


@pytest.fixture(scope="module")
def balances(fixture_data: dict[str, Any], expenses: list[Expense]) -> dict[str, MemberBalance]:
    return compute_balances(fixture_data["members"], expenses)


def test_fixture_sanity(fixture_data: dict[str, Any], expenses: list[Expense]) -> None:
    assert fixture_data["members"] == MEMBERS
    amounts = [e["amount"] for e in fixture_data["expenses"]]
    assert sum(amounts) == fixture_data["sheet"]["total"] == 28_614_000
    assert all(sum(e.shares.values()) == e.amount for e in expenses)


def test_nets_sum_to_zero(balances: dict[str, MemberBalance]) -> None:
    assert sum(b.net for b in balances.values()) == 0


@pytest.mark.parametrize("member", MEMBERS)
def test_close_to_the_sheet(
    member: str, fixture_data: dict[str, Any], balances: dict[str, MemberBalance]
) -> None:
    sheet = fixture_data["sheet"]
    assert abs(balances[member].share - sheet["per_member_total"][member]) <= TOLERANCE
    assert abs(balances[member].net - sheet["nets"][member]) <= TOLERANCE


@pytest.mark.parametrize("member", MEMBERS)
def test_pinned_balances(member: str, balances: dict[str, MemberBalance]) -> None:
    balance = balances[member]
    assert (balance.paid, balance.share, balance.net) == PINNED[member]
    assert balance.contributed == balance.sent == balance.received == 0


def test_settle(balances: dict[str, MemberBalance]) -> None:
    nets = {m: b.net for m, b in balances.items()}
    transfers = settle(nets)
    assert transfers == PINNED_TRANSFERS
    assert len(transfers) <= 5
    after = dict(nets)
    for t in transfers:
        assert nets[t.payer] < 0 < nets[t.payee]
        after[t.payer] += t.amount
        after[t.payee] -= t.amount
    assert all(v == 0 for v in after.values())
    assert sum(t.amount for t in transfers) == sum(n for n in nets.values() if n > 0)
