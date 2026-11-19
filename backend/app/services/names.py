import re
import unicodedata
from collections.abc import Sequence

from app.domain.ascii_text import strip_diacritics

_WHITESPACE_RUN = re.compile(r"\s+")
_ACCOUNT_NAME = re.compile(r"[A-Z]+(?: [A-Z]+)*")
MAX_ACCOUNT_NAME_LENGTH = 50
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cs", "Co"})
# Joiners are part of valid emoji sequences; the other format characters (bidi overrides,
# zero-width spaces, BOM) only serve to spoof or hide text.
_ALLOWED_FORMAT_CHARS = frozenset({"‌", "‍"})


def _is_forbidden(char: str) -> bool:
    category = unicodedata.category(char)
    if category == "Cf":
        return char not in _ALLOWED_FORMAT_CHARS
    return category in _FORBIDDEN_CATEGORIES


def normalise_name(raw: str, max_length: int) -> str:
    """Normalize to NFC, forbid control characters, collapse whitespace, and check bounds."""
    composed = unicodedata.normalize("NFC", raw)
    if any(_is_forbidden(char) for char in composed):
        raise ValueError("control characters are not allowed")
    name = _WHITESPACE_RUN.sub(" ", composed).strip()
    if not 1 <= len(name) <= max_length:
        raise ValueError(f"must be 1 to {max_length} characters")
    return name


def normalise_text(raw: str, max_length: int, *, multiline: bool = False) -> str | None:
    """Normalize optional text to NFC, trim outer whitespace, and return None when empty."""
    composed = unicodedata.normalize("NFC", raw.replace("\r\n", "\n") if multiline else raw)
    if any(_is_forbidden(char) and not (multiline and char == "\n") for char in composed):
        raise ValueError("control characters are not allowed")
    text = composed.strip()
    if len(text) > max_length:
        raise ValueError(f"must be at most {max_length} characters")
    return text or None


def has_duplicate_names(names: Sequence[str]) -> bool:
    """Return True when two normalized names collide ignoring case."""
    folded = {unicodedata.normalize("NFC", name.casefold()) for name in names}
    return len(folded) != len(names)


def normalise_account_name(raw: str) -> str:
    """Format an account holder name as uppercase ASCII letters separated by single spaces."""
    folded = _WHITESPACE_RUN.sub(" ", strip_diacritics(raw)).strip().upper()
    if len(folded) > MAX_ACCOUNT_NAME_LENGTH or _ACCOUNT_NAME.fullmatch(folded) is None:
        raise ValueError(f"must be 1 to {MAX_ACCOUNT_NAME_LENGTH} letters and spaces")
    return folded
