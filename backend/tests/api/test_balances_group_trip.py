"""The anonymized 6-member trip fixture settled end-to-end through the HTTP API."""

import json
from typing import Any

import pytest
from httpx import AsyncClient

from tests.api.test_balances import get_balances, transfers
from tests.api.test_expenses_create import created, group_trip
from tests.domain.test_group_trip_regression import FIXTURE, MEMBERS, PINNED, PINNED_TRANSFERS

pytestmark = pytest.mark.anyio


def api_split(split: dict[str, Any], ids: dict[str, str]) -> dict[str, Any]:
    """Rewrite fixture member names into created trip member UUIDs."""
    if split["mode"] == "equal":
        return {"mode": "equal", "participants": [ids[name] for name in split["participants"]]}
    return {
        "mode": "exact",
        "amounts": {ids[name]: amount for name, amount in split["amounts"].items()},
    }


async def enter_group_trip(client: AsyncClient) -> tuple[str, dict[str, str]]:
    """Create the trip and post every fixture expense via the HTTP API."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    trip_id, member_ids = await group_trip(client)
    ids = dict(zip(MEMBERS, member_ids, strict=True))
    assert len(data["expenses"]) == 42
    for item in data["expenses"]:
        body = {
            "title": item["title"],
            "amount": item["amount"],
            "category": "other",
            "spent_on": "2026-11-07",
            "paid_by": ids[item["paid_by"]],
            "split": api_split(item["split"], ids),
        }
        await created(client, trip_id, body)
    return trip_id, ids


async def test_group_trip_balances_and_transfers_match_the_pinned_results(
    client: AsyncClient,
) -> None:
    trip_id, ids = await enter_group_trip(client)

    sheet = await get_balances(client, trip_id)

    by_name = dict(zip(MEMBERS, sheet["members"], strict=True))
    assert {name: (m["paid"], m["share"], m["net"]) for name, m in by_name.items()} == PINNED
    assert all(m["contributed"] == 0 and not m["removed"] for m in sheet["members"])
    assert sheet["fund"] == {"holder_id": None, "remaining": 0}
    names = {value: name for name, value in ids.items()}
    assert [(names[p], names[q], a) for p, q, a in transfers(sheet)] == [
        (t.payer, t.payee, t.amount) for t in PINNED_TRANSFERS
    ]
