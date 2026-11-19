import uuid

import pytest

from app.services.errors import RuleViolation
from app.services.expenses import compute_split, order_by_position

A, B, C = (uuid.UUID(int=n) for n in (3, 1, 2))
POSITIONS = {A: 0, B: 1, C: 2}


def test_weights_are_ordered_by_position_not_by_id_or_request_order() -> None:
    ordered = order_by_position({C: 5, B: 0, A: 7}, POSITIONS)

    assert list(ordered.items()) == [(A, 7), (B, 0), (C, 5)]


def test_an_id_outside_the_active_members_is_member_not_active() -> None:
    with pytest.raises(RuleViolation) as raised:
        order_by_position({A: 1, uuid.UUID(int=9): 1}, POSITIONS)

    assert raised.value.code == "member_not_active"


def test_equal_leftover_follows_the_given_order() -> None:
    assert compute_split("equal", 100, {A: 1, B: 1, C: 1}) == [34, 33, 33]
    assert compute_split("equal", 100, {C: 1, B: 1, A: 1}) == [34, 33, 33]


@pytest.mark.parametrize(
    ("mode", "weights", "difference"),
    [
        ("exact", {A: 40, B: 50}, 10),
        ("exact", {A: 60, B: 50}, -10),
        ("percent", {A: 5000, B: 4000}, None),
        ("shares", {A: 0, B: 0}, None),
    ],
)
def test_split_errors_become_invalid_split_without_domain_text(
    mode: str, weights: dict[uuid.UUID, int], difference: int | None
) -> None:
    with pytest.raises(RuleViolation) as raised:
        compute_split(mode, 100, weights)

    assert (raised.value.code, raised.value.difference) == ("invalid_split", difference)
    assert str(A) not in str(raised.value)
