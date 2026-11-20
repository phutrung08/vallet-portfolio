"""Regression guard: no ``{trip_id}`` route without ``require_member``."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from httpx import ASGITransport, AsyncClient

from app.api.deps import require_member
from app.core.config import Settings
from app.main import create_app
from tests.api.conftest import CSRF_HEADERS
from tests.api.routes import served_routes
from tests.api.test_expenses_create import created, expense_body
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio

# Routes with {trip_id} intentionally outside membership authz; currently none.
UNGUARDED_BY_DESIGN: frozenset[tuple[str, str]] = frozenset()

NAME_BODY = {"display_name": "Dung"}
# Payer and participant are unknown to the victim trip; 404 must run before any 409 check.
EXPENSE_BODY = {
    "title": "Coffee",
    "amount": 50_000,
    "category": "food",
    "spent_on": "2026-11-07",
    "paid_by": "00000000-0000-4000-8000-000000000001",
    "split": {"mode": "equal", "participants": ["00000000-0000-4000-8000-000000000001"]},
}
CONTRIBUTION_BODY = {
    "member_id": "00000000-0000-4000-8000-000000000001",
    "amount": 100_000,
    "contributed_on": "2026-11-07",
}
PAYMENT_BODY = {
    "payer": "00000000-0000-4000-8000-000000000001",
    "payee": "00000000-0000-4000-8000-000000000002",
    "amount": 100_000,
    "paid_on": "2026-11-08",
}
BANK_ACCOUNT_BODY = {"bank_bin": "970436", "account_number": "0123456789", "account_name": "An"}

# Every served {trip_id} route must appear here with a minimal valid body.
REQUEST_BODIES: dict[tuple[str, str], dict[str, Any] | None] = {
    ("GET", "/trips/{trip_id}"): None,
    ("GET", "/trips/{trip_id}/share-link"): None,
    ("POST", "/trips/{trip_id}/share-link/rotate"): None,
    ("POST", "/trips/{trip_id}/close"): None,
    ("POST", "/trips/{trip_id}/reopen"): None,
    ("POST", "/trips/{trip_id}/lock"): None,
    ("POST", "/trips/{trip_id}/unlock"): None,
    ("POST", "/trips/{trip_id}/members"): NAME_BODY,
    ("PATCH", "/trips/{trip_id}/members/{member_id}"): NAME_BODY,
    ("DELETE", "/trips/{trip_id}/members/{member_id}"): None,
    ("POST", "/trips/{trip_id}/leave"): None,
    ("POST", "/trips/{trip_id}/expenses"): EXPENSE_BODY,
    ("GET", "/trips/{trip_id}/expenses"): None,
    ("GET", "/trips/{trip_id}/expenses/days"): None,
    ("GET", "/trips/{trip_id}/expenses/{expense_id}"): None,
    ("PUT", "/trips/{trip_id}/expenses/{expense_id}"): EXPENSE_BODY | {"version": 1},
    ("DELETE", "/trips/{trip_id}/expenses/{expense_id}"): None,
    ("GET", "/trips/{trip_id}/balances"): None,
    ("GET", "/trips/{trip_id}/summary"): None,
    ("GET", "/trips/{trip_id}/fund"): None,
    ("PUT", "/trips/{trip_id}/fund"): {"holder_id": None},
    ("POST", "/trips/{trip_id}/fund/contributions"): CONTRIBUTION_BODY,
    ("DELETE", "/trips/{trip_id}/fund/contributions/{contribution_id}"): None,
    ("GET", "/trips/{trip_id}/payments"): None,
    ("POST", "/trips/{trip_id}/payments"): PAYMENT_BODY,
    ("DELETE", "/trips/{trip_id}/payments/{payment_id}"): None,
    ("PUT", "/trips/{trip_id}/members/me/bank-account"): BANK_ACCOUNT_BODY,
    ("DELETE", "/trips/{trip_id}/members/me/bank-account"): None,
    ("GET", "/trips/{trip_id}/bank-accounts"): None,
    ("GET", "/trips/{trip_id}/events"): None,
    # Query parameters omitted intentionally so membership 404 precedes query validation.
    ("GET", "/trips/{trip_id}/vietqr"): None,
}


def trip_routes(app: FastAPI) -> Iterator[tuple[str, str, Dependant]]:
    """Yield every ``(method, path, dependant)`` scoped by ``{trip_id}``."""
    for method, path, dependant in served_routes(app):
        if "{trip_id}" in path and (method, path) not in UNGUARDED_BY_DESIGN:
            yield method, path, dependant


def depends_on_require_member(dependant: Dependant) -> bool:
    return any(
        sub.call is require_member or depends_on_require_member(sub)
        for sub in dependant.dependencies
    )


ROUTES = list(trip_routes(create_app(Settings(_env_file=None, environment="development"))))


def test_there_are_trip_routes_to_audit() -> None:
    assert len(ROUTES) >= len(REQUEST_BODIES)


def test_every_trip_route_depends_on_require_member() -> None:
    unguarded = [
        f"{method} {path}"
        for method, path, dependant in ROUTES
        if not depends_on_require_member(dependant)
    ]

    assert unguarded == []


def test_the_registry_has_no_stale_entries() -> None:
    assert set(REQUEST_BODIES) == {(method, path) for method, path, _ in ROUTES}


@pytest.mark.parametrize(
    ("method", "path"),
    [(method, path) for method, path, _ in ROUTES],
    ids=[f"{method} {path}" for method, path, _ in ROUTES],
)
async def test_outsiders_and_anonymous_callers_get_the_standard_404(
    app: FastAPI, client: AsyncClient, other_client: AsyncClient, method: str, path: str
) -> None:
    if (method, path) not in REQUEST_BODIES:
        pytest.fail(f"{method} {path} has no entry in REQUEST_BODIES; add a minimal valid body")
    victim = await create(client)
    await create(other_client)
    member_ids = [m["id"] for m in victim["members"]]
    expense = await created(
        client,
        victim["id"],
        expense_body(member_ids[0], {"mode": "equal", "participants": member_ids}),
    )
    payment_body = PAYMENT_BODY | {"payer": member_ids[1], "payee": member_ids[0]}
    payment = await client.post(f"/trips/{victim['id']}/payments", json=payment_body)
    url = path.format(
        trip_id=victim["id"],
        member_id=member_ids[1],
        expense_id=expense["id"],
        contribution_id=uuid.uuid4(),
        payment_id=payment.json()["id"],
    )
    body = REQUEST_BODIES[(method, path)]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test", headers=CSRF_HEADERS
    ) as nobody:
        responses = [
            await caller.request(method, url, json=body) for caller in (other_client, nobody)
        ]

    assert [r.status_code for r in responses] == [404, 404]
    assert [r.json() for r in responses] == [NOT_FOUND, NOT_FOUND]
