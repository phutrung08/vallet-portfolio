import base64
import hashlib
import hmac
import secrets
import uuid

import pytest

from app.core.security import derive_share_token, hash_token, is_well_formed_token, new_token


def test_new_tokens_are_well_formed_and_distinct() -> None:
    tokens = {new_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(len(token) == 43 and is_well_formed_token(token) for token in tokens)


def test_hash_is_the_32_byte_sha256_digest() -> None:
    token = new_token()

    assert len(hash_token(token)) == 32
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != hash_token(new_token())


@pytest.mark.parametrize(
    "token",
    [
        "",
        "a" * 42,
        "a" * 44,
        "a" * 42 + "=",
        "a" * 42 + "+",
        "a" * 42 + "/",
        "a" * 42 + " ",
        "a" * 42 + "\n",
        "a" * 42 + "é",
        "a" * 21 + ";" + "a" * 21,
        secrets.token_hex(32),
    ],
)
def test_malformed_tokens_are_rejected(token: str) -> None:
    assert not is_well_formed_token(token)


def test_all_url_safe_characters_are_accepted() -> None:
    assert is_well_formed_token("ABCxyz019-_" + "Q" * 32)


SHARE_KEY = b"k" * 48
TRIP_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def test_share_token_is_deterministic_and_well_formed() -> None:
    token = derive_share_token(SHARE_KEY, TRIP_ID, 1)

    assert token == derive_share_token(SHARE_KEY, TRIP_ID, 1)
    assert len(token) == 43 and is_well_formed_token(token)


def test_share_token_changes_with_version_trip_and_key() -> None:
    token = derive_share_token(SHARE_KEY, TRIP_ID, 1)

    assert derive_share_token(SHARE_KEY, TRIP_ID, 2) != token
    assert derive_share_token(SHARE_KEY, uuid.uuid4(), 1) != token
    assert derive_share_token(b"j" * 48, TRIP_ID, 1) != token


def test_share_token_is_the_documented_hmac() -> None:
    message = f"share:v1:{TRIP_ID}:3".encode()
    digest = hmac.new(SHARE_KEY, message, hashlib.sha256).digest()

    expected = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    assert derive_share_token(SHARE_KEY, TRIP_ID, 3) == expected
