"""Split an expense total among participants. Amounts are integer minor units."""

from collections.abc import Mapping, Sequence

from app.domain.money import allocate

type MemberId = str

FULL_BASIS_POINTS = 10_000  # 100%; 1% = 100 basis points


class SplitError(ValueError):
    """Raised when an expense cannot be split as requested."""


def _require_participants(participants: Sequence[MemberId]) -> None:
    if not participants:
        raise SplitError("participants must not be empty")
    seen: set[MemberId] = set()
    for member in participants:
        if member in seen:
            raise SplitError(f"duplicate participant: {member!r}")
        seen.add(member)


def split_equal(total: int, participants: Sequence[MemberId]) -> dict[MemberId, int]:
    """Split ``total`` equally among ``participants``; the parts sum to ``total``.

    Leftover units go one each to the earliest participants in the given order,
    so the caller must pass a stable order. Keys follow ``participants``.
    """
    if total < 0:
        raise SplitError(f"total must be >= 0, got {total}")
    _require_participants(participants)
    amounts = allocate(total, [1] * len(participants))
    return dict(zip(participants, amounts, strict=True))


def _require_valid_mapping(total: int, values: Mapping[MemberId, int], name: str) -> None:
    """Checks shared by the mapping-based splits: ``total >= 0``, non-empty, no negative value."""
    if total < 0:
        raise SplitError(f"total must be >= 0, got {total}")
    if not values:
        raise SplitError(f"{name} must not be empty")
    negative = {member: value for member, value in values.items() if value < 0}
    if negative:
        raise SplitError(f"{name} must be >= 0, got {negative}")


def split_by_shares(total: int, shares: Mapping[MemberId, int]) -> dict[MemberId, int]:
    """Split ``total`` proportionally to integer ``shares``; the parts sum to ``total``.

    ``{"a": 2, "b": 1}`` means a pays two parts to b's one. A member with 0 shares
    pays 0. Leftover units follow the largest-remainder rule of ``allocate``.
    Keys follow ``shares``.
    """
    _require_valid_mapping(total, shares, "shares")
    if total > 0 and not any(shares.values()):
        raise SplitError("cannot split a positive total when all shares are zero")
    amounts = allocate(total, list(shares.values()))
    return dict(zip(shares, amounts, strict=True))


def split_by_percent(total: int, basis_points: Mapping[MemberId, int]) -> dict[MemberId, int]:
    """Split ``total`` by percentages given as integer basis points (1% = 100).

    The basis points must sum to exactly ``FULL_BASIS_POINTS`` (100%). The parts
    sum to ``total``; leftover units follow the largest-remainder rule of
    ``allocate``. Keys follow ``basis_points``.
    """
    _require_valid_mapping(total, basis_points, "basis points")
    points_sum = sum(basis_points.values())
    if points_sum != FULL_BASIS_POINTS:
        raise SplitError(f"basis points must sum to {FULL_BASIS_POINTS}, got {points_sum}")
    amounts = allocate(total, list(basis_points.values()))
    return dict(zip(basis_points, amounts, strict=True))


def split_exact(total: int, amounts: Mapping[MemberId, int]) -> dict[MemberId, int]:
    """Validate amounts stated per member and return a copy; they must sum to ``total``.

    The error message gives the difference so the UI can show what is missing
    (``sum < total``) or in excess (``sum > total``). Keys follow ``amounts``.
    """
    _require_valid_mapping(total, amounts, "amounts")
    amounts_sum = sum(amounts.values())
    if amounts_sum != total:
        raise SplitError(
            f"amounts sum to {amounts_sum} but total is {total}: difference {total - amounts_sum}"
        )
    return dict(amounts)
