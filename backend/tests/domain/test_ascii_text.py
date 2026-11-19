import unicodedata

import pytest

from app.domain.ascii_text import strip_diacritics


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("Nguyễn Văn Đức", "Nguyen Van Duc"),
        ("Đà Lạt", "Da Lat"),
        ("đường Hồ Xuân Hương", "duong Ho Xuan Huong"),
        ("Hợp", "Hop"),
        ("Café 2026!", "Cafe 2026!"),
        ("東京", "東京"),
    ],
)
def test_strip_diacritics(raw: str, folded: str) -> None:
    assert strip_diacritics(raw) == folded


def test_decomposed_input_folds_the_same() -> None:
    assert strip_diacritics(unicodedata.normalize("NFD", "Nguyễn Văn Đức")) == "Nguyen Van Duc"
