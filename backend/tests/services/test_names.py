import unicodedata

import pytest

from app.services.names import (
    has_duplicate_names,
    normalise_account_name,
    normalise_name,
    normalise_text,
)

NFD_HOP = unicodedata.normalize("NFD", "Hợp")


def test_decomposed_vietnamese_becomes_composed() -> None:
    assert NFD_HOP != "Hợp"
    assert normalise_name(NFD_HOP, 40) == "Hợp"


def test_whitespace_is_trimmed_and_collapsed() -> None:
    assert normalise_name("  Nguyễn \u00a0  Văn\u3000A  ", 40) == "Nguyễn Văn A"


@pytest.mark.parametrize("raw", ["", "   ", "\u00a0"])
def test_blank_names_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="1 to 40"):
        normalise_name(raw, 40)


def test_length_is_counted_after_normalisation() -> None:
    assert normalise_name(unicodedata.normalize("NFD", "ợ" * 40), 40) == "ợ" * 40
    with pytest.raises(ValueError, match="1 to 40"):
        normalise_name("a" * 41, 40)


@pytest.mark.parametrize(
    "raw", ["a\x00b", "a\tb", "a\nb", "a\x7fb", "a\u202eb", "a\u200bb", "\ufeffa"]
)
def test_control_and_invisible_characters_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="control"):
        normalise_name(raw, 40)


def test_emoji_joiners_survive() -> None:
    assert normalise_name("👨\u200d👩", 40) == "👨\u200d👩"


def test_duplicates_ignore_case_and_composition() -> None:
    assert has_duplicate_names(["Hợp", "HỢP"])
    assert has_duplicate_names(["An", "Bình", "bình"])
    assert not has_duplicate_names(["An", "Bình"])
    assert not has_duplicate_names([])


def test_text_is_composed_trimmed_and_empty_becomes_none() -> None:
    assert normalise_text(f"  {NFD_HOP}  market ", 200) == "Hợp  market"
    assert normalise_text("  \u3000 ", 200) is None


def test_multiline_text_keeps_newlines_as_lf() -> None:
    assert normalise_text("a\r\nb\n\nc\r\n", 500, multiline=True) == "a\nb\n\nc"


@pytest.mark.parametrize(
    ("raw", "multiline"),
    [("a\nb", False), ("a\rb", True), ("a\tb", True), ("a\u202eb", True)],
)
def test_other_control_characters_are_rejected_in_text(raw: str, multiline: bool) -> None:
    with pytest.raises(ValueError, match="control"):
        normalise_text(raw, 500, multiline=multiline)


def test_text_length_is_checked_after_trimming() -> None:
    assert normalise_text(" " + "x" * 200 + " ", 200) == "x" * 200
    with pytest.raises(ValueError, match="at most 200"):
        normalise_text("x" * 201, 200)


@pytest.mark.parametrize(
    ("raw", "normalised"),
    [
        ("Nguyễn Văn Đức", "NGUYEN VAN DUC"),
        (NFD_HOP, "HOP"),
        ("  trần   thị\tbích  ", "TRAN THI BICH"),
        ("A" * 50, "A" * 50),
    ],
)
def test_account_name_is_uppercase_ascii_as_banks_print_it(raw: str, normalised: str) -> None:
    assert normalise_account_name(raw) == normalised


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "A" * 51, "Nguyễn Văn 2", "O'Brien", "Lê-Anh", "東京", "Søren", "An\u200bh"],
)
def test_account_name_refuses_anything_but_letters_and_spaces(raw: str) -> None:
    with pytest.raises(ValueError, match="letters and spaces"):
        normalise_account_name(raw)
