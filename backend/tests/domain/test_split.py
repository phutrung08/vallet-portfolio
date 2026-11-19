import pytest

from app.domain.split import SplitError, split_by_percent, split_by_shares, split_equal, split_exact

SIX = ["an", "binh", "chi", "dung", "em", "giang"]


@pytest.mark.parametrize(
    ("total", "participants", "expected"),
    [
        (300_000, SIX, dict.fromkeys(SIX, 50_000)),
        (
            359_000,
            ["an", "dung", "em", "giang"],
            dict.fromkeys(["an", "dung", "em", "giang"], 89_750),
        ),
        (
            130_000,
            SIX,
            {
                "an": 21_667,
                "binh": 21_667,
                "chi": 21_667,
                "dung": 21_667,
                "em": 21_666,
                "giang": 21_666,
            },
        ),
        (160_000, ["dung"], {"dung": 160_000}),
        (0, SIX, dict.fromkeys(SIX, 0)),
    ],
)
def test_split_equal_real_cases(
    total: int, participants: list[str], expected: dict[str, int]
) -> None:
    result = split_equal(total, participants)
    assert result == expected
    assert list(result) == participants
    assert sum(result.values()) == total
    assert max(result.values()) - min(result.values()) <= 1


@pytest.mark.parametrize(
    ("total", "participants", "message"),
    [
        (-1, SIX, "total must be >= 0"),
        (100, [], "participants must not be empty"),
        (100, ["an", "binh", "an"], "'an'"),
    ],
)
def test_split_equal_rejects_invalid_input(
    total: int, participants: list[str], message: str
) -> None:
    with pytest.raises(SplitError, match=message):
        split_equal(total, participants)
    assert issubclass(SplitError, ValueError)


REAL_SHARES = {"an": 588, "binh": 724, "chi": 724, "dung": 588, "em": 588, "giang": 588}


@pytest.mark.parametrize(
    ("total", "shares", "expected"),
    [
        (300_000, {"a": 2, "b": 1}, {"a": 200_000, "b": 100_000}),
        (100, {"a": 1, "b": 1, "c": 1}, {"a": 34, "b": 33, "c": 33}),
        (100, {"a": 1, "b": 0, "c": 1}, {"a": 50, "b": 0, "c": 50}),
        (
            3_800_000,
            REAL_SHARES,
            {
                "an": 588_000,
                "binh": 724_000,
                "chi": 724_000,
                "dung": 588_000,
                "em": 588_000,
                "giang": 588_000,
            },
        ),
        (0, {"a": 0, "b": 0}, {"a": 0, "b": 0}),
    ],
)
def test_split_by_shares_cases(
    total: int, shares: dict[str, int], expected: dict[str, int]
) -> None:
    result = split_by_shares(total, shares)
    assert result == expected
    assert list(result) == list(shares)
    assert sum(result.values()) == total


@pytest.mark.parametrize(
    ("total", "shares", "message"),
    [
        (-1, {"a": 1}, "total must be >= 0"),
        (100, {}, "shares must not be empty"),
        (100, {"a": 1, "b": -1}, "shares must be >= 0"),
        (100, {"a": 0, "b": 0}, "all shares are zero"),
    ],
)
def test_split_by_shares_rejects_invalid_input(
    total: int, shares: dict[str, int], message: str
) -> None:
    with pytest.raises(SplitError, match=message):
        split_by_shares(total, shares)


@pytest.mark.parametrize(
    ("total", "basis_points", "expected"),
    [
        (200_000, {"a": 5_000, "b": 5_000}, {"a": 100_000, "b": 100_000}),
        (
            100_000,
            {"a": 3_333, "b": 3_333, "c": 3_334},
            {"a": 33_330, "b": 33_330, "c": 33_340},
        ),
        (101, {"a": 3_333, "b": 3_333, "c": 3_334}, {"a": 34, "b": 33, "c": 34}),
        (100, {"a": 10_000, "b": 0}, {"a": 100, "b": 0}),
        (0, {"a": 2_500, "b": 7_500}, {"a": 0, "b": 0}),
    ],
)
def test_split_by_percent_cases(
    total: int, basis_points: dict[str, int], expected: dict[str, int]
) -> None:
    result = split_by_percent(total, basis_points)
    assert result == expected
    assert list(result) == list(basis_points)
    assert sum(result.values()) == total


@pytest.mark.parametrize(
    ("total", "basis_points", "message"),
    [
        (-1, {"a": 10_000}, "total must be >= 0"),
        (100, {}, "basis points must not be empty"),
        (100, {"a": 11_000, "b": -1_000}, "basis points must be >= 0"),
        (100, {"a": 5_000, "b": 4_999}, "must sum to 10000, got 9999"),
        (100, {"a": 5_000, "b": 5_001}, "must sum to 10000, got 10001"),
    ],
)
def test_split_by_percent_rejects_invalid_input(
    total: int, basis_points: dict[str, int], message: str
) -> None:
    with pytest.raises(SplitError, match=message):
        split_by_percent(total, basis_points)


@pytest.mark.parametrize(
    ("total", "amounts"),
    [
        (3_800_000, {k: v * 1_000 for k, v in REAL_SHARES.items()}),
        (100, {"a": 70, "b": 30}),
        (100, {"a": 100, "b": 0}),
        (0, {"a": 0}),
    ],
)
def test_split_exact_cases(total: int, amounts: dict[str, int]) -> None:
    result = split_exact(total, amounts)
    assert result == amounts
    assert list(result) == list(amounts)
    assert sum(result.values()) == total


def test_split_exact_returns_a_copy() -> None:
    amounts = {"a": 60, "b": 40}
    result = split_exact(100, amounts)
    result["a"] = 0
    assert amounts == {"a": 60, "b": 40}


@pytest.mark.parametrize(
    ("total", "amounts", "message"),
    [
        (-1, {"a": 0}, "total must be >= 0"),
        (100, {}, "amounts must not be empty"),
        (100, {"a": 110, "b": -10}, "amounts must be >= 0"),
        (100, {"a": 60, "b": 30}, "sum to 90 but total is 100: difference 10"),
        (100, {"a": 60, "b": 45}, "sum to 105 but total is 100: difference -5"),
    ],
)
def test_split_exact_rejects_invalid_input(
    total: int, amounts: dict[str, int], message: str
) -> None:
    with pytest.raises(SplitError, match=message):
        split_exact(total, amounts)
