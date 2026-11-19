from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient, Response
from starlette.responses import PlainTextResponse
from starlette.types import Receive, Scope, Send

from app.api.rate_limit import RateLimitMiddleware
from app.core import limits

pytestmark = pytest.mark.anyio

RATE_LIMITED = {"code": "rate_limited", "message": "Too many requests"}
CLIENT_IP = "203.0.113.7"


@dataclass
class FakeClock:
    now: float = 1_000.0

    def __call__(self) -> float:
        return self.now


async def ok(scope: Scope, receive: Receive, send: Send) -> None:
    await PlainTextResponse("ok")(scope, receive, send)


@pytest.fixture(autouse=True)
def small_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "RATE_WINDOW_SECONDS", 60)
    monkeypatch.setattr(limits, "RATE_LIMIT_ALL", 6)
    monkeypatch.setattr(limits, "RATE_LIMIT_JOIN", 2)
    monkeypatch.setattr(limits, "RATE_LIMIT_TRIP_CREATE", 5)
    monkeypatch.setattr(limits, "RATE_LIMIT_WRITES", 3)
    monkeypatch.setattr(limits, "RATE_LIMIT_TRACKED_KEYS", 4)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def client_for(limiter: RateLimitMiddleware, ip: str = CLIENT_IP) -> AsyncClient:
    transport = ASGITransport(app=limiter, client=(ip, 50_000))
    return AsyncClient(transport=transport, base_url="https://test")


@pytest.fixture
def limiter(clock: FakeClock) -> RateLimitMiddleware:
    return RateLimitMiddleware(ok, trust_proxy_headers=False, clock=clock)


def statuses(responses: list[Response]) -> list[int]:
    return [r.status_code for r in responses]


async def test_join_has_its_own_tighter_limit_and_normalizes_paths(
    limiter: RateLimitMiddleware,
) -> None:
    async with client_for(limiter) as client:
        joins = [
            await client.post(path) for path in ("/join", "https://test//join/preview/", "/join/")
        ]
        other_write = await client.post("/trips/x/expenses")

    assert statuses(joins) == [200, 200, 429]
    assert joins[2].json() == RATE_LIMITED
    assert other_write.status_code == 200


async def test_trip_create_has_its_own_tighter_limit_and_normalizes_paths(
    limiter: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "RATE_LIMIT_TRIP_CREATE", 2)
    async with client_for(limiter) as client:
        creates = [
            await client.post(path) for path in ("/trips", "/trips/", "https://test//trips//")
        ]
        other_write = await client.put("/trips/x/fund")

    assert statuses(creates) == [200, 200, 429]
    assert creates[2].json() == RATE_LIMITED
    assert other_write.status_code == 200


async def test_writes_share_a_limit_reads_do_not_spend_it(limiter: RateLimitMiddleware) -> None:
    async with client_for(limiter) as client:
        writes = [
            await client.post("/trips"),
            await client.put("/trips/x/fund"),
            await client.delete("/trips/x/expenses/y"),
            await client.patch("/trips/x/members/y"),
        ]
        read = await client.get("/trips/x")

    assert statuses(writes) == [200, 200, 200, 429]
    assert read.status_code == 200


async def test_every_request_spends_from_the_overall_limit(limiter: RateLimitMiddleware) -> None:
    async with client_for(limiter) as client:
        responses = [await client.get("/health") for _ in range(7)]

    assert statuses(responses) == [200] * 6 + [429]


async def test_a_refused_request_spends_nothing(limiter: RateLimitMiddleware) -> None:
    async with client_for(limiter) as client:
        joins = [await client.post("/join") for _ in range(4)]
        reads = [await client.get("/health") for _ in range(5)]

    # Two joins passed; the refused two left the overall bucket at 4.
    assert statuses(joins) == [200, 200, 429, 429]
    assert statuses(reads) == [200] * 4 + [429]


async def test_retry_after_is_the_whole_seconds_until_a_token(
    limiter: RateLimitMiddleware, clock: FakeClock
) -> None:
    async with client_for(limiter) as client:
        await client.post("/join")
        await client.post("/join")
        clock.now += 10.5
        refused = await client.post("/join")

    # Two per 60 s is one token per 30 s; 10.5 s of it have passed.
    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "20"


async def test_the_limit_recovers_as_the_window_passes(
    limiter: RateLimitMiddleware, clock: FakeClock
) -> None:
    async with client_for(limiter) as client:
        spent = [await client.post("/join") for _ in range(3)]
        clock.now += 30
        one_back = [await client.post("/join") for _ in range(2)]
        clock.now += 600
        full = [await client.post("/join") for _ in range(3)]

    assert statuses(spent) == [200, 200, 429]
    assert statuses(one_back) == [200, 429]
    assert statuses(full) == [200, 200, 429]


async def test_ips_are_limited_separately(limiter: RateLimitMiddleware) -> None:
    async with client_for(limiter, "198.51.100.1") as first, client_for(limiter) as second:
        mine = [await first.post("/join") for _ in range(3)]
        theirs = await second.post("/join")

    assert statuses(mine) == [200, 200, 429]
    assert theirs.status_code == 200


async def test_forwarded_for_is_ignored_by_default(limiter: RateLimitMiddleware) -> None:
    async with client_for(limiter) as client:
        responses = [
            await client.post("/join", headers={"X-Forwarded-For": f"192.0.2.{n}"})
            for n in range(3)
        ]

    assert statuses(responses) == [200, 200, 429]


async def test_a_trusted_proxy_keys_on_the_last_forwarded_hop(clock: FakeClock) -> None:
    limiter = RateLimitMiddleware(ok, trust_proxy_headers=True, clock=clock)

    async with client_for(limiter, "10.0.0.2") as proxy:
        # The client may put anything in front; the proxy appends the address it saw.
        spoofed = [
            await proxy.post("/join", headers={"X-Forwarded-For": f"192.0.2.{n}, 198.51.100.9"})
            for n in range(3)
        ]
        another_client = await proxy.post("/join", headers={"X-Forwarded-For": "198.51.100.10"})
        no_header = [await proxy.post("/join") for _ in range(3)]

    assert statuses(spoofed) == [200, 200, 429]
    assert another_client.status_code == 200
    assert statuses(no_header) == [200, 200, 429]


async def test_memory_is_bounded_by_dropping_the_least_recently_used(
    limiter: RateLimitMiddleware,
) -> None:
    async with client_for(limiter) as kept:
        await kept.post("/join")
        await kept.post("/join")
        refused: list[Response] = []
        for n in range(10):
            async with client_for(limiter, f"192.0.2.{n}") as passing:
                await passing.get("/health")
            # Refused, so it spends nothing, but it keeps this IP's buckets recently used.
            refused.append(await kept.post("/join"))

    assert len(limiter.buckets) == limits.RATE_LIMIT_TRACKED_KEYS
    assert statuses(refused) == [429] * 10
