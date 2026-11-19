"""Per-IP rate limits as token buckets.

Every request spends a token from the IP's "all" bucket, plus one from its "join" bucket
(POST /join, /join/preview), its "trip_create" + "write" buckets (POST /trips), or its "write"
bucket (every other state-changing request). A request is refused, spending nothing, when any of
its buckets is empty.
"""

import math
import re
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.csrf import WRITE_METHODS
from app.api.errors import error_response
from app.core import limits

JOIN_PATHS = frozenset({"/join", "/join/preview"})
TRIP_CREATE_PATH = "/trips"
UNKNOWN_CLIENT = "unknown"

type BucketKey = tuple[str, str]  # (rule, client IP)


@dataclass
class Bucket:
    tokens: float
    refilled_at: float


class TokenBuckets:
    """Bounded LRU store of per-key token buckets."""

    def __init__(self, window: float, max_keys: int, clock: Callable[[], float]) -> None:
        self._window = window
        self._max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[BucketKey, Bucket] = OrderedDict()

    def __len__(self) -> int:
        return len(self._buckets)

    def admit(self, wanted: list[tuple[BucketKey, int]]) -> int:
        """Spend one token from each bucket and return 0, or wait seconds until all refill."""
        now = self._clock()
        buckets = [(self._refilled(key, limit, now), limit) for key, limit in wanted]
        waits = [(1 - b.tokens) * self._window / limit for b, limit in buckets if b.tokens < 1]
        if waits:
            return max(1, math.ceil(max(waits)))
        for bucket, _ in buckets:
            bucket.tokens -= 1
        return 0

    def _refilled(self, key: BucketKey, limit: int, now: float) -> Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._buckets[key] = Bucket(float(limit), now)
            if len(self._buckets) > self._max_keys:
                self._buckets.popitem(last=False)
        else:
            self._buckets.move_to_end(key)
            gained = (now - bucket.refilled_at) * limit / self._window
            bucket.tokens = min(float(limit), bucket.tokens + gained)
            bucket.refilled_at = now
        return bucket


def _normalize_path(path: str) -> str:
    collapsed = re.sub(r"/+", "/", path)
    if not collapsed or collapsed == "/":
        return "/"
    return collapsed.rstrip("/")


def client_ip(scope: Scope, trust_proxy_headers: bool) -> str:
    """Return socket peer IP, or the last X-Forwarded-For hop appended by our trusted proxy."""
    if trust_proxy_headers:
        forwarded = b",".join(v for name, v in scope["headers"] if name == b"x-forwarded-for")
        hops = [hop.strip() for hop in forwarded.decode("latin-1").split(",") if hop.strip()]
        if hops:
            return hops[-1]
    client = scope.get("client")
    return str(client[0]) if client else UNKNOWN_CLIENT


def wanted_buckets(method: str, path: str, ip: str) -> list[tuple[BucketKey, int]]:
    """Select the rate-limit buckets consumed by ``method`` on ``path``."""
    normalized = _normalize_path(path)
    wanted = [(("all", ip), limits.RATE_LIMIT_ALL)]
    if method == "POST" and normalized in JOIN_PATHS:
        wanted.append((("join", ip), limits.RATE_LIMIT_JOIN))
    elif method in WRITE_METHODS:
        wanted.append((("write", ip), limits.RATE_LIMIT_WRITES))
        if method == "POST" and normalized == TRIP_CREATE_PATH:
            wanted.append((("trip_create", ip), limits.RATE_LIMIT_TRIP_CREATE))
    return wanted


class RateLimitMiddleware:
    """ASGI middleware enforcing per-IP token-bucket rate limits."""

    def __init__(
        self,
        app: ASGIApp,
        trust_proxy_headers: bool,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self._trust_proxy_headers = trust_proxy_headers
        self.buckets = TokenBuckets(
            limits.RATE_WINDOW_SECONDS, limits.RATE_LIMIT_TRACKED_KEYS, clock
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ip = client_ip(scope, self._trust_proxy_headers)
        wait = self.buckets.admit(wanted_buckets(scope["method"], scope["path"], ip))
        if wait:
            headers = {"Retry-After": str(wait)}
            response = error_response(429, "rate_limited", "Too many requests", headers)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
