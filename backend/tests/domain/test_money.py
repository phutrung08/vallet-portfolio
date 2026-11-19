import random

import pytest

from app.domain.money import AllocationError, allocate


def _generate_cases() -> list[tuple[int, list[int]]]:
    rng = random.Random(20261114)  # noqa: S311 -- deterministic test data, not security
    cases: list[tuple[int, list[int]]] = []
    for _ in range(300):
        total = rng.choice([0, rng.randint(0, 100), rng.randint(0, 10**7), rng.randint(0, 10**12)])
        weights = [
            rng.choice([0, rng.randint(1, 10), rng.randint(1, 1000)])
            for _ in range(rng.randint(1, 50))
        ]
        if sum(weights) == 0:
            weights[0] = 1
        cases.append((total, weights))
    return cases


CASES = _generate_cases()


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (130_000, [1] * 6, [21_667, 21_667, 21_667, 21_667, 21_666, 21_666]),
        (850_000, [1] * 6, [141_667, 141_667, 141_667, 141_667, 141_666, 141_666]),
        (708_000, [1, 1, 1, 1, 0, 1], [141_600, 141_600, 141_600, 141_600, 0, 141_600]),
        (359_000, [1, 0, 0, 1, 1, 1], [89_750, 0, 0, 89_750, 89_750, 89_750]),
        (100, [1, 1, 1], [34, 33, 33]),
        (0, [1, 2, 3], [0, 0, 0]),
        (0, [0, 0], [0, 0]),
        (123_456, [7], [123_456]),
    ],
)
def test_concrete_cases(total: int, weights: list[int], expected: list[int]) -> None:
    assert allocate(total, weights) == expected


def test_weighted_trip_case() -> None:
    weights = [588, 724, 724, 588, 588, 588]
    result = allocate(3_800_000, weights)
    _assert_properties(3_800_000, weights, result)
    assert result[1] == result[2]
    assert result[0] < result[1]


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (5, [1, 1, 1, 1], [2, 1, 1, 1]),
        (2, [1, 1, 1, 1], [1, 1, 0, 0]),
        (10, [1, 2, 1, 2], [2, 3, 2, 3]),
        (3, [0, 1, 1, 1, 1], [0, 1, 1, 1, 0]),
    ],
)
def test_ties_go_to_lower_index(total: int, weights: list[int], expected: list[int]) -> None:
    assert allocate(total, weights) == expected


@pytest.mark.parametrize(
    ("total", "weights"),
    [(-1, [1, 1]), (10, []), (0, []), (10, [1, -1]), (10, [0, 0, 0])],
)
def test_invalid_input_raises(total: int, weights: list[int]) -> None:
    with pytest.raises(AllocationError):
        allocate(total, weights)


def test_allocation_error_is_value_error() -> None:
    assert issubclass(AllocationError, ValueError)


def _assert_properties(total: int, weights: list[int], result: list[int]) -> None:
    s = sum(weights)
    assert sum(result) == total
    assert len(result) == len(weights)
    assert all(part >= 0 for part in result)
    assert all(abs(part * s - total * w) < s for part, w in zip(result, weights, strict=True))
    assert all(part == 0 for part, w in zip(result, weights, strict=True) if w == 0)


@pytest.mark.parametrize(("total", "weights"), CASES)
def test_properties(total: int, weights: list[int]) -> None:
    result = allocate(total, weights)
    _assert_properties(total, weights, result)
    assert allocate(total, list(weights)) == result
    assert allocate(total, [w * 37 for w in weights]) == result


@pytest.mark.parametrize(("total", "weights"), CASES)
def test_equal_weights_differ_by_at_most_one(total: int, weights: list[int]) -> None:
    result = allocate(total, [3] * len(weights))
    assert max(result) - min(result) <= 1
