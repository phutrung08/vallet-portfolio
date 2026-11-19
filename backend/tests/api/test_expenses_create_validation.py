from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient

from tests.api.test_expenses_create import expense_body, group_trip, post_expense

pytestmark = pytest.mark.anyio

type BodyChange = Callable[[list[str]], dict[str, Any]]


def equal(ids: list[str]) -> dict[str, Any]:
    return {"mode": "equal", "participants": ids}


INVALID: dict[str, BodyChange] = {
    "amount zero": lambda ids: {"amount": 0},
    "amount negative": lambda ids: {"amount": -1},
    "amount above 10**12": lambda ids: {"amount": 10**12 + 1},
    "amount boolean": lambda ids: {"amount": True},
    "amount float": lambda ids: {"amount": 708_000.0},
    "amount string": lambda ids: {"amount": "708000"},
    "unknown category": lambda ids: {"category": "Food"},
    "unknown mode": lambda ids: {"split": {"mode": "weird", "participants": ids}},
    "unknown field": lambda ids: {"currency": "VND"},
    "unknown split field": lambda ids: {"split": equal(ids) | {"amounts": {}}},
    "missing paid_by": lambda ids: {"paid_by": ...},
    "duplicate participant": lambda ids: {"split": equal([ids[0], ids[1], ids[0]])},
    "duplicate participant, other case": lambda ids: {"split": equal([ids[0], ids[0].upper()])},
    "duplicate key, other case": lambda ids: {
        "split": {"mode": "shares", "shares": {ids[0]: 1, ids[0].upper(): 1}}
    },
    "empty participants": lambda ids: {"split": equal([])},
    "empty shares": lambda ids: {"split": {"mode": "shares", "shares": {}}},
    "boolean share": lambda ids: {"split": {"mode": "shares", "shares": {ids[0]: True}}},
    "negative share": lambda ids: {"split": {"mode": "shares", "shares": {ids[0]: -1}}},
    "share above 10000": lambda ids: {"split": {"mode": "shares", "shares": {ids[0]: 10_001}}},
    "basis points above 10000": lambda ids: {
        "split": {"mode": "percent", "basis_points": {ids[0]: 10_001}}
    },
    "exact above 10**12": lambda ids: {"split": {"mode": "exact", "amounts": {ids[0]: 10**12 + 1}}},
    "participant not a uuid": lambda ids: {"split": equal(["An"])},
    "title only whitespace": lambda ids: {"title": "  　 "},
    "title too long": lambda ids: {"title": "x" * 121},
    "note with a control character": lambda ids: {"note": "a\tb"},
    "note with a lone carriage return": lambda ids: {"note": "a\rb"},
    "note too long": lambda ids: {"note": "x" * 501},
    "place with a newline": lambda ids: {"place": "a\nb"},
    "place too long": lambda ids: {"place": "x" * 201},
    "bad date": lambda ids: {"spent_on": "2026-02-30"},
}


@pytest.mark.parametrize("change", INVALID.values(), ids=INVALID.keys())
async def test_invalid_bodies_are_422(client: AsyncClient, change: BodyChange) -> None:
    trip_id, ids = await group_trip(client)
    body = {k: v for k, v in (expense_body(ids[0], equal(ids)) | change(ids)).items() if v != ...}

    response = await post_expense(client, trip_id, body)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"


async def test_more_than_fifty_participants_is_422(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    too_many = [f"00000000-0000-4000-8000-{n:012d}" for n in range(51)]

    response = await post_expense(client, trip_id, expense_body(ids[0], equal(too_many)))

    assert (response.status_code, response.json()["fields"]) == (
        422,
        ["body.split.equal.participants"],
    )
