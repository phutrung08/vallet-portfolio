import base64
import hashlib
import hmac
import re
import secrets
from uuid import UUID

TOKEN_BYTES = 32
# token_urlsafe(32) is unpadded base64url of 32 bytes, so every token we mint has 43 characters.
TOKEN_PATTERN = r"[A-Za-z0-9_-]{43}"  # noqa: S105 - a regex, not a secret
_TOKEN_SHAPE = re.compile(TOKEN_PATTERN)


def new_token() -> str:
    """Mint a 256-bit URL-safe random token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def is_well_formed_token(token: str) -> bool:
    """Return True when ``token`` matches the exact 43-character base64url shape."""
    return _TOKEN_SHAPE.fullmatch(token) is not None


def hash_token(token: str) -> bytes:
    # The token is 256 random bits, so it cannot be guessed offline even from its hash; a slow
    # salted hash (bcrypt/argon2) would only add CPU per request and rule out an index lookup.
    return hashlib.sha256(token.encode()).digest()


def derive_share_token(key: bytes, trip_id: UUID, version: int) -> str:
    """Derive the share token for ``version``; bumping the version invalidates the old link."""
    message = f"share:v1:{trip_id}:{version}".encode()
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
