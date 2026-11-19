"""Vietnamese text folded to plain ASCII, the form banks print on accounts and VietQR carries."""

import unicodedata

# "đ" is a letter of its own, not "d" plus a mark, so NFD leaves it alone.
_STROKED_D = str.maketrans({"đ": "d", "Đ": "D"})


def strip_diacritics(text: str) -> str:
    """Turns "Nguyễn Văn Đức" into "Nguyen Van Duc"; characters with no ASCII base are kept."""
    decomposed = unicodedata.normalize("NFD", text.translate(_STROKED_D))
    return "".join(char for char in decomposed if not unicodedata.combining(char))
