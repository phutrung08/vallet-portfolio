"""AES-256-GCM for personal data at rest.

A blob is ``key version (1 byte) || nonce (12 bytes) || ciphertext and tag``. The version byte is
authenticated along with the caller's AAD, which names the row the value belongs to, so a blob
copied into another row, or relabelled with another version, fails to decrypt.
"""

import base64
import binascii
import secrets
from collections.abc import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
KEY_VERSION = 1
NONCE_BYTES = 12
TAG_BYTES = 16
_HEADER_BYTES = 1 + NONCE_BYTES


class DecryptionError(Exception):
    """The blob is malformed, was tampered with, or was sealed under another key or AAD."""


def parse_key(encoded: str) -> bytes:
    """Decode a base64url key (padding optional); raise ValueError unless 32 bytes."""
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        key = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("key is not base64url") from None
    if len(key) != KEY_BYTES:
        raise ValueError(f"key must be {KEY_BYTES} bytes")
    return key


def encrypt(key: bytes, plaintext: str, aad: bytes, *, version: int = KEY_VERSION) -> bytes:
    """Encrypt ``plaintext`` with AES-256-GCM under ``key`` and authenticate ``version || aad``."""
    if not 0 <= version <= 255:
        raise ValueError("key version must fit in one byte (0-255)")
    if len(key) != KEY_BYTES:
        raise ValueError(f"key must be {KEY_BYTES} bytes")
    header = bytes([version]) + secrets.token_bytes(NONCE_BYTES)
    sealed = AESGCM(key).encrypt(header[1:], plaintext.encode("utf-8"), header[:1] + aad)
    return header + sealed


def decrypt(key: bytes | Mapping[int, bytes], blob: bytes, aad: bytes) -> str:
    """Verify and decrypt ``blob`` using a single key (v1) or a versioned key ring."""
    if len(blob) < _HEADER_BYTES + TAG_BYTES:
        raise DecryptionError
    version = blob[0]
    if isinstance(key, bytes):
        if version != KEY_VERSION:
            raise DecryptionError
        raw_key: bytes | None = key
    else:
        raw_key = key.get(version)
    if raw_key is None or len(raw_key) != KEY_BYTES:
        raise DecryptionError
    nonce, sealed = blob[1:_HEADER_BYTES], blob[_HEADER_BYTES:]
    try:
        plaintext = AESGCM(raw_key).decrypt(nonce, sealed, blob[:1] + aad)
    except InvalidTag:
        raise DecryptionError from None
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        raise DecryptionError from None
