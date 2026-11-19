import binascii

import pytest

from app.domain.vietqr import (
    MAX_AMOUNT,
    VietQrError,
    build_transfer_payload,
    crc16_ccitt_false,
    tlv,
    transfer_message,
)

# Built once by build_transfer_payload, its CRC checked with binascii.crc_hqx, then pinned.
PINNED = (
    "000201010212"
    "3854"
    "0010A000000727"
    "0124" "0006970436" "01100123456789"
    "0208QRIBFTTA"
    "5303704"
    "54072409918"
    "5802VN"
    "62180814VL Da Lat 2026"
    "6304B26C"
)  # fmt: skip

# The worked examples in NAPAS's VietQR format document v1.0, section 6.1, with their CRCs.
NAPAS_EXAMPLES = {
    "static to account": (
        "00020101021138570010A00000072701270006970403011200110123456780208QRIBFTTA"
        "53037045802VN6304",
        "F4E5",
    ),
    "static to card": (
        "00020101021138600010A00000072701300006970403011697040311012345670208QRIBFTTC"
        "53037045802VN6304",
        "4F52",
    ),
    "dynamic to account": (
        "00020101021238570010A00000072701270006970403011300110123456780208QRIBFTTA"
        "530370454061800005802VN62340107NPS68690819thanh toan don hang6304",
        "2E2E",
    ),
    "dynamic to card": (
        "00020101021238600010A00000072701300006970403011697040311012345670208QRIBFTTC"
        "530370454061800005802VN62340107NPS68690819thanh toan don hang6304",
        "A203",
    ),
}


def parse_tlv(data: str) -> dict[str, str]:
    """ID -> value for one level of EMVCo TLV; fails on a truncated or overlong object."""
    fields: dict[str, str] = {}
    at = 0
    while at < len(data):
        tag, length = data[at : at + 2], int(data[at + 2 : at + 4])
        value = data[at + 4 : at + 4 + length]
        assert len(value) == length, f"field {tag} is truncated"
        fields[tag] = value
        at += 4 + length
    return fields


def test_crc_of_the_standard_check_string() -> None:
    assert crc16_ccitt_false(b"123456789") == 0x29B1


@pytest.mark.parametrize(("unsigned", "crc"), NAPAS_EXAMPLES.values(), ids=NAPAS_EXAMPLES.keys())
def test_crc_matches_the_napas_examples(unsigned: str, crc: str) -> None:
    assert f"{crc16_ccitt_false(unsigned.encode()):04X}" == crc


def test_tlv_lengths_are_two_digits() -> None:
    assert tlv("08", "VL Da Lat") == "0809VL Da Lat"
    assert tlv("00", "A000000727") == "0010A000000727"
    assert tlv("62", "x" * 99) == "6299" + "x" * 99
    with pytest.raises(VietQrError):
        tlv("62", "x" * 100)
    with pytest.raises(VietQrError):
        tlv("62", "")


def test_the_payload_for_a_fixed_transfer_is_pinned() -> None:
    payload = build_transfer_payload("970436", "0123456789", 2_409_918, "VL Da Lat 2026")

    assert payload == PINNED
    assert f"{binascii.crc_hqx(payload[:-4].encode(), 0xFFFF):04X}" == payload[-4:]
    assert f"{crc16_ccitt_false(payload[:-4].encode()):04X}" == payload[-4:]


def test_the_payload_decodes_back_to_its_inputs() -> None:
    payload = build_transfer_payload("970422", "0011223344556677889", MAX_AMOUNT, "A" * 25)

    root = parse_tlv(payload)
    assert list(root) == ["00", "01", "38", "53", "54", "58", "62", "63"]
    assert (root["00"], root["01"], root["53"], root["58"]) == ("01", "12", "704", "VN")
    assert root["54"] == str(MAX_AMOUNT)
    account = parse_tlv(root["38"])
    assert (account["00"], account["02"]) == ("A000000727", "QRIBFTTA")
    assert parse_tlv(account["01"]) == {"00": "970422", "01": "0011223344556677889"}
    assert parse_tlv(root["62"]) == {"08": "A" * 25}


@pytest.mark.parametrize(
    ("bank_bin", "account", "amount", "message"),
    [
        ("97043", "0123456789", 1, "VL"),
        ("97043A", "0123456789", 1, "VL"),
        ("970436", "12345", 1, "VL"),
        ("970436", "1" * 20, 1, "VL"),
        ("970436", "0123 456789", 1, "VL"),
        ("970436", "0123456789", 0, "VL"),
        ("970436", "0123456789", -1, "VL"),
        ("970436", "0123456789", MAX_AMOUNT + 1, "VL"),
        ("970436", "0123456789", True, "VL"),
        ("970436", "0123456789", 1, ""),
        ("970436", "0123456789", 1, "A" * 26),
        ("970436", "0123456789", 1, "Đà Lạt"),
        ("970436", "0123456789", 1, "VL-Da-Lat"),
    ],
)
def test_invalid_inputs_raise(bank_bin: str, account: str, amount: int, message: str) -> None:
    with pytest.raises(VietQrError):
        build_transfer_payload(bank_bin, account, amount, message)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("VL Đà Lạt", "VL Da Lat"),
        ("VL Hội An – Huế 🎉 (2026)", "VL Hoi An Hue 2026"),
        ("VL Phú Quốc mùa hè cùng gia đình", "VL Phu Quoc mua he cung g"),
        ("VL 東京", "VL"),
    ],
)
def test_transfer_message_is_ascii_and_fits(text: str, message: str) -> None:
    assert transfer_message(text) == message
    assert len(message) <= 25
