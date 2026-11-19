"""Money primitives. Amounts are integer minor units; nothing here uses floats."""

from collections.abc import Sequence


class AllocationError(ValueError):
    """Raised when an amount cannot be allocated over the given weights."""


def allocate(total: int, weights: Sequence[int]) -> list[int]:
    """Split ``total`` into integer parts proportional to ``weights``, summing to ``total``.

    Largest-remainder method in exact integer arithmetic: each part first gets
    ``total * w // sum(weights)``. The units lost to flooring (fewer than
    ``len(weights)``) then go one each to the parts with the largest remainder
    ``total * w % sum(weights)``. Equal remainders are broken by lower index
    first, so the result is deterministic. A zero weight has a zero remainder
    and the leftover count never exceeds the number of positive remainders, so
    it always gets 0.
    """
    if total < 0:
        raise AllocationError(f"total must be >= 0, got {total}")
    if not weights:
        raise AllocationError("weights must not be empty")
    if any(w < 0 for w in weights):
        raise AllocationError(f"weights must be >= 0, got {list(weights)}")
    weight_sum = sum(weights)
    if weight_sum == 0:
        if total > 0:
            raise AllocationError("cannot allocate a positive total over all-zero weights")
        return [0] * len(weights)

    parts = [total * w // weight_sum for w in weights]
    remainders = [total * w % weight_sum for w in weights]
    leftover = total - sum(parts)
    by_remainder = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in by_remainder[:leftover]:
        parts[i] += 1
    return parts
