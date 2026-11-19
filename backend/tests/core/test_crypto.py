import base64
import secrets
from collections.abc import Callable

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.crypto import (
    KEY_VERSION,
    NONCE_BYTES,
    DecryptionError,
    decrypt,
    encrypt,
    parse_key,
)

KEY = secrets.token_bytes(32)
AAD = b"bank:v1:trip:member"
NUMBER = "0123456789012"


def test_round_trip() -> None:
    blob = encrypt(KEY, NUMBER, AAD)

    assert decrypt(KEY, blob, AAD) == NUMBER


def test_blob_is_version_nonce_ciphertext_and_tag() -> None:
    blob = encrypt(KEY, NUMBER, AAD)

    assert blob[0] == KEY_VERSION
    assert len(blob) == 1 + NONCE_BYTES + len(NUMBER) + 16
    assert NUMBER.encode() not in blob


def test_two_encryptions_of_one_value_use_different_nonces() -> None:
    first, second = encrypt(KEY, NUMBER, AAD), encrypt(KEY, NUMBER, AAD)

    assert first[1 : 1 + NONCE_BYTES] != second[1 : 1 + NONCE_BYTES]
    assert first != second


def _flip(blob: bytes, index: int) -> bytes:
    return blob[:index] + bytes([blob[index] ^ 1]) + blob[index + 1 :]


@pytest.mark.parametrize(
    ("key", "aad", "tamper"),
    [
        (secrets.token_bytes(32), AAD, lambda b: b),
        (KEY, b"bank:v1:trip:other-member", lambda b: b),
        (KEY, AAD, lambda b: _flip(b, len(b) - 1)),
        (KEY, AAD, lambda b: _flip(b, 5)),
        (KEY, AAD, lambda b: bytes([KEY_VERSION + 1]) + b[1:]),
        (KEY, AAD, lambda b: b[:20]),
        (KEY, AAD, lambda b: b""),
    ],
    ids=[
        "wrong key",
        "wrong aad",
        "tampered tag",
        "tampered nonce",
        "other version",
        "cut",
        "empty",
    ],
)
def test_anything_but_the_right_key_aad_and_blob_fails(
    key: bytes, aad: bytes, tamper: Callable[[bytes], bytes]
) -> None:
    blob = tamper(encrypt(KEY, NUMBER, AAD))

    with pytest.raises(DecryptionError):
        decrypt(key, blob, aad)


def test_key_ring_decrypts_multiple_versions_and_rejects_unknown_version() -> None:
    key_v1 = secrets.token_bytes(32)
    key_v2 = secrets.token_bytes(32)
    ring = {1: key_v1, 2: key_v2}

    blob_v1 = encrypt(key_v1, NUMBER, AAD, version=1)
    blob_v2 = encrypt(key_v2, "9988776655", AAD, version=2)
    blob_v3 = encrypt(secrets.token_bytes(32), "1122334455", AAD, version=3)

    assert decrypt(ring, blob_v1, AAD) == NUMBER
    assert decrypt(ring, blob_v2, AAD) == "9988776655"
    with pytest.raises(DecryptionError):
        decrypt(ring, blob_v3, AAD)


def test_invalid_utf8_plaintext_raises_decryption_error() -> None:
    nonce = secrets.token_bytes(NONCE_BYTES)
    header = bytes([KEY_VERSION])
    sealed = AESGCM(KEY).encrypt(nonce, b"\xff\xfe", header + AAD)
    blob = header + nonce + sealed

    with pytest.raises(DecryptionError):
        decrypt(KEY, blob, AAD)


@pytest.mark.parametrize("version", [-1, 256])
def test_encrypt_rejects_out_of_range_version(version: int) -> None:
    with pytest.raises(ValueError, match="version"):
        encrypt(KEY, NUMBER, AAD, version=version)


def test_encrypt_rejects_wrong_key_length() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt(b"short", NUMBER, AAD)


def test_parse_key_accepts_padded_and_unpadded_base64url() -> None:
    encoded = base64.urlsafe_b64encode(KEY).decode()

    assert parse_key(encoded) == KEY
    assert parse_key(encoded.rstrip("=")) == KEY
    assert parse_key(secrets.token_urlsafe(32)) != KEY


@pytest.mark.parametrize(
    "encoded",
    [
        base64.urlsafe_b64encode(b"k" * 31).decode(),
        base64.urlsafe_b64encode(b"k" * 33).decode(),
        "",
        "not base64 at all!" * 3,
    ],
    ids=["short", "long", "empty", "garbage"],
)
def test_parse_key_refuses_anything_but_32_base64url_bytes(encoded: str) -> None:
    with pytest.raises(ValueError, match="key"):
        parse_key(encoded)
