import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.core.config import Settings
from app.core.security import derive_share_token, hash_token, is_well_formed_token
from app.repositories.models import Member, Membership, Trip
from tests.api.conftest import CSRF_HEADERS

pytestmark = pytest.mark.anyio

NOT_FOUND = {"code": "not_found", "message": "Not Found"}
DETAIL_KEYS = {
    "id",
    "name",
    "currency",
    "starts_on",
    "ends_on",
    "fund_holder_id",
    "locked",
    "closed",
    "me",
    "members",
}
MEMBER_KEYS = {"id", "display_name", "position", "removed"}


def body(**overrides: Any) -> dict[str, Any]:
    return {"name": "Phu Quoc", "creator_name": "An", "member_names": ["Binh", "Chi"]} | overrides


async def create(client: AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post("/trips", json=body(**overrides))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def test_create_returns_the_detail_and_sets_the_device_cookie(
    client: AsyncClient, settings: Settings
) -> None:
    response = await client.post("/trips", json=body())

    assert response.status_code == 201
    assert settings.device_cookie_name in response.headers["set-cookie"]
    detail = response.json()
    assert set(detail) == DETAIL_KEYS
    assert detail["currency"] == "VND"
    assert (detail["starts_on"], detail["ends_on"]) == (None, None)
    assert (detail["locked"], detail["closed"], detail["fund_holder_id"]) == (False, False, None)
    assert [(m["display_name"], m["position"], m["removed"]) for m in detail["members"]] == [
        ("An", 0, False),
        ("Binh", 1, False),
        ("Chi", 2, False),
    ]
    assert all(set(m) == MEMBER_KEYS for m in detail["members"])
    assert detail["me"] == detail["members"][0]["id"]


async def test_creator_is_attached_to_the_device_and_the_trip_is_readable(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)

    membership = await session.scalar(
        select(Membership).where(Membership.trip_id == uuid.UUID(detail["id"]))
    )
    assert membership is not None
    assert str(membership.member_id) == detail["me"]
    fetched = await client.get(f"/trips/{detail['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == detail


async def test_fund_holder_is_the_creator_only_when_the_trip_uses_a_fund(
    client: AsyncClient,
) -> None:
    with_fund = await create(client, uses_fund=True)
    without_fund = await create(client, uses_fund=False)

    assert with_fund["fund_holder_id"] == with_fund["me"]
    assert without_fund["fund_holder_id"] is None


async def test_dates_and_currency_are_stored(client: AsyncClient) -> None:
    detail = await create(client, currency="USD", starts_on="2026-03-01", ends_on="2026-03-01")

    assert (detail["currency"], detail["starts_on"], detail["ends_on"]) == (
        "USD",
        "2026-03-01",
        "2026-03-01",
    )


async def test_names_are_normalised_to_nfc_with_collapsed_whitespace(
    client: AsyncClient,
) -> None:
    decomposed = unicodedata.normalize("NFD", "Hợp")
    assert decomposed != "Hợp"

    detail = await create(
        client,
        name="  Phu   Quoc \u00a0 2026 ",
        creator_name=decomposed,
        member_names=["  Binh   An "],
    )

    assert detail["name"] == "Phu Quoc 2026"
    assert [m["display_name"] for m in detail["members"]] == ["Hợp", "Binh An"]
    assert detail["members"][0]["display_name"] == unicodedata.normalize("NFC", "Hợp")


@pytest.mark.parametrize(
    "overrides",
    [
        {"creator_name": "An", "member_names": ["an"]},
        {"member_names": ["Binh", "BINH"]},
        {"creator_name": unicodedata.normalize("NFD", "Hợp"), "member_names": ["hợp"]},
        {"creator_name": "Hợp", "member_names": [unicodedata.normalize("NFD", "HỢP")]},
        {"creator_name": "An", "member_names": ["  An  "]},
    ],
)
async def test_duplicate_member_names_are_rejected(
    client: AsyncClient, overrides: dict[str, Any]
) -> None:
    response = await client.post("/trips", json=body(**overrides))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["fields"] == ["body.member_names"]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"starts_on": "2026-03-02", "ends_on": "2026-03-01"}, "body.ends_on"),
        ({"member_names": [f"Member {i}" for i in range(50)]}, "body.member_names"),
        ({"uses_fund": "true"}, "body.uses_fund"),
        ({"uses_fund": 1}, "body.uses_fund"),
        ({"surprise": 1}, "body.surprise"),
        ({"currency": "EUR"}, "body.currency"),
        ({"currency": "vnd"}, "body.currency"),
        ({"name": "   "}, "body.name"),
        ({"name": "x" * 81}, "body.name"),
        ({"name": "Phu\x00Quoc"}, "body.name"),
        ({"name": "Phu\nQuoc"}, "body.name"),
        ({"name": "Phu\u202eQuoc"}, "body.name"),
        ({"creator_name": ""}, "body.creator_name"),
        ({"creator_name": "x" * 41}, "body.creator_name"),
        ({"member_names": [""]}, "body.member_names.0"),
        ({"member_names": ["x" * 41]}, "body.member_names.0"),
    ],
)
async def test_invalid_requests_are_422_with_the_field_path(
    client: AsyncClient, overrides: dict[str, Any], field: str
) -> None:
    response = await client.post("/trips", json=body(**overrides))

    assert response.status_code == 422
    assert field in response.json()["fields"]
    assert "set-cookie" not in response.headers


async def test_fifty_members_in_total_is_allowed(client: AsyncClient) -> None:
    detail = await create(client, member_names=[f"Member {i}" for i in range(49)])

    assert len(detail["members"]) == 50


async def test_device_trip_cap_is_enforced(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_TRIPS_PER_DEVICE", 2)
    await create(client, name="Trip 1")
    await create(client, name="Trip 2")

    refused = await client.post("/trips", json=body(name="Trip 3"))

    assert refused.status_code == 409
    assert refused.json()["code"] == "device_trip_limit_reached"


async def test_get_trip_flags_removed_members_and_keeps_position_order(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await session.execute(
        update(Member)
        .where(Member.trip_id == uuid.UUID(detail["id"]), Member.position == 1)
        .values(removed_at=datetime.now(UTC))
    )

    fetched = (await client.get(f"/trips/{detail['id']}")).json()

    assert [(m["position"], m["removed"]) for m in fetched["members"]] == [
        (0, False),
        (1, True),
        (2, False),
    ]


async def test_get_trip_is_404_for_non_members_and_unknown_trips_alike(
    app: FastAPI, client: AsyncClient, other_client: AsyncClient
) -> None:
    detail = await create(client)
    await create(other_client)

    not_member = await other_client.get(f"/trips/{detail['id']}")
    missing = await other_client.get(f"/trips/{uuid.uuid4()}")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test", headers=CSRF_HEADERS
    ) as anon:
        no_cookie = await anon.get(f"/trips/{detail['id']}")

    assert not_member.status_code == missing.status_code == no_cookie.status_code == 404
    assert not_member.json() == missing.json() == no_cookie.json() == NOT_FOUND
    assert not_member.content == missing.content


async def test_get_trip_with_a_malformed_id_is_422(client: AsyncClient) -> None:
    response = await client.get("/trips/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["fields"] == ["path.trip_id"]


async def test_share_link_matches_the_derivation_and_the_stored_hash(
    client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail = await create(client)

    response = await client.get(f"/trips/{detail['id']}/share-link")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    link = response.json()
    assert set(link) == {"token", "version"}
    assert link["version"] == 1
    assert len(link["token"]) == 43 and is_well_formed_token(link["token"])
    trip_id = uuid.UUID(detail["id"])
    assert link["token"] == derive_share_token(settings.share_link_key_bytes, trip_id, 1)
    stored = await session.scalar(select(Trip.share_token_hash).where(Trip.id == trip_id))
    assert stored == hash_token(link["token"])


async def test_share_link_follows_the_stored_version(
    client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail = await create(client)
    trip_id = uuid.UUID(detail["id"])
    await session.execute(update(Trip).where(Trip.id == trip_id).values(share_token_version=2))

    link = (await client.get(f"/trips/{detail['id']}/share-link")).json()

    assert link["version"] == 2
    assert link["token"] == derive_share_token(settings.share_link_key_bytes, trip_id, 2)


async def test_share_link_is_404_for_non_members(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail = await create(client)
    await create(other_client)

    foreign = await other_client.get(f"/trips/{detail['id']}/share-link")
    missing = await other_client.get(f"/trips/{uuid.uuid4()}/share-link")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == NOT_FOUND
