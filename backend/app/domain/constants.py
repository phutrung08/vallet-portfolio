"""Domain-level category and split-mode definitions shared across layers."""

from typing import Literal, get_args

ExpenseCategory = Literal["food", "transport", "lodging", "activity", "shopping", "other"]
EXPENSE_CATEGORIES: tuple[str, ...] = get_args(ExpenseCategory)

SplitMode = Literal["equal", "shares", "percent", "exact"]
SPLIT_MODES: tuple[str, ...] = get_args(SplitMode)
