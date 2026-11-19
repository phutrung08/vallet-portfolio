"""VietQR payloads: the EMVCo merchant-presented QR string that prefills a bank transfer.

Layout per NAPAS, "Tài liệu quy định về định dạng mã VietQR trong dịch vụ chuyển nhanh NAPAS247",
version 1.0 (09/2021), sections 5 and 6.1.3 (dynamic QR to an account). Every data object is
ID (2 digits), length (2 digits), value:

    00 "01"  payload format          01 "12"  dynamic (carries an amount)
    38       beneficiary: 00 GUID "A000000727", 01 (00 BIN, 01 account number), 02 "QRIBFTTA"
    53 "704" VND                     54       amount        58 "VN"
    62       additional data: 08 purpose of transaction
    63       CRC-16/CCITT-FALSE over everything before its value, "6304" included

The app never moves money (SECURITY.md section 8): this only prefills the payer's own app.
"""

import re

from app.domain.ascii_text import strip_diacritics

NAPAS_GUID = "A000000727"
TRANSFER_TO_ACCOUNT = "QRIBFTTA"
VND_NUMERIC_CODE = "704"
MAX_AMOUNT = 9_999_999_999_999  # field 54 holds at most 13 characters
MAX_MESSAGE_LENGTH = 25  # field 62-08 (purpose of transaction)
MAX_VALUE_LENGTH = 99

_BIN = re.compile(r"[0-9]{6}")
_ACCOUNT_NUMBER = re.compile(r"[0-9]{6,19}")
_MESSAGE = re.compile(r"[A-Za-z0-9 ]{1,25}")
_NOT_MESSAGE_CHARS = re.compile(r"[^A-Za-z0-9]+")


class VietQrError(ValueError):
    """An input the payload cannot carry."""


def crc16_ccitt_false(data: bytes) -> int:
    """Polynomial 0x1021, initial 0xFFFF, no reflection, no final XOR (ISO/IEC 13239)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def tlv(tag: str, value: str) -> str:
    if not 1 <= len(value) <= MAX_VALUE_LENGTH:
        raise VietQrError(f"field {tag} must be 1 to {MAX_VALUE_LENGTH} characters")
    return f"{tag}{len(value):02d}{value}"


def transfer_message(text: str) -> str:
    """``text`` as a transfer message: ASCII letters, digits and single spaces, at most 25."""
    words = _NOT_MESSAGE_CHARS.sub(" ", strip_diacritics(text)).split()
    return " ".join(words)[:MAX_MESSAGE_LENGTH].rstrip()


def _validate(bank_bin: str, account_number: str, amount: int, message: str) -> None:
    if _BIN.fullmatch(bank_bin) is None:
        raise VietQrError("bank BIN must be 6 digits")
    if _ACCOUNT_NUMBER.fullmatch(account_number) is None:
        raise VietQrError("account number must be 6 to 19 digits")
    if isinstance(amount, bool) or not 1 <= amount <= MAX_AMOUNT:
        raise VietQrError(f"amount must be 1 to {MAX_AMOUNT}")
    if _MESSAGE.fullmatch(message) is None:
        raise VietQrError("message must be 1 to 25 ASCII letters, digits or spaces")


def build_transfer_payload(bank_bin: str, account_number: str, amount: int, message: str) -> str:
    """The payload for a one-off transfer of ``amount`` VND to the account."""
    _validate(bank_bin, account_number, amount, message)
    beneficiary = tlv("00", bank_bin) + tlv("01", account_number)
    account_info = tlv("00", NAPAS_GUID) + tlv("01", beneficiary) + tlv("02", TRANSFER_TO_ACCOUNT)
    unsigned = (
        tlv("00", "01")
        + tlv("01", "12")
        + tlv("38", account_info)
        + tlv("53", VND_NUMERIC_CODE)
        + tlv("54", str(amount))
        + tlv("58", "VN")
        + tlv("62", tlv("08", message))
        + "6304"
    )
    return unsigned + f"{crc16_ccitt_false(unsigned.encode('ascii')):04X}"
