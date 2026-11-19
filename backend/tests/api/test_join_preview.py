import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Executable, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import derive_share_token, hash_token
from app.repositories.models import Member, Trip
from tests.api.conftest import CSRF_HEADERS, FrozenClock
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio


async def share_token(client: AsyncClient, trip_id: str) -> str:
    response = await client.get(f"/trips/{trip_id}/share-link")
    assert response.status_code == 200
    token: str = response.json()["token"]
    return token


async def shared_trip(client: AsyncClient, **overrides: Any) -> tuple[dict[str, Any], str]:
    """Create a trip with ``client`` (members An, Binh, Chi) and return its share token."""
    detail = await create(client, **overrides)
    return detail, await share_token(client, detail["id"])


async def persist(session: AsyncSession, statement: Executable) -> None:
    """Run ``statement`` and commit the test savepoint so subsequent 4xx rollbacks keep it."""
    await session.execute(statement)
    await session.commit()


async def remove_member(session: AsyncSession, trip_id: str, position: int) -> None:
    await persist(
        session,
        update(Member)
        .where(Member.trip_id == uuid.UUID(trip_id), Member.position == position)
        .values(removed_at=datetime.now(UTC)),
    )


async def test_preview_shows_the_trip_and_members_without_creating_a_device(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail, token = await shared_trip(client, currency="USD", starts_on="2026-03-01")

    response = await other_client.post("/join/preview", json={"token": token})

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "trip": {
            "id": detail["id"],
            "name": "Phu Quoc",
            "currency": "USD",
            "starts_on": "2026-03-01",
            "ends_on": None,
            "locked": False,
            "closed": False,
        },
        "members": [
            {"id": m["id"], "display_name": m["display_name"], "joined": position == 0}
            for position, m in enumerate(detail["members"])
        ],
        "me": None,
    }


async def test_preview_sets_me_for_a_device_already_in_the_trip(client: AsyncClient) -> None:
    detail, token = await shared_trip(client)

    preview = (await client.post("/join/preview", json={"token": token})).json()

    assert preview["me"] == detail["me"]


async def test_preview_hides_removed_members_and_flags_joined_ones(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    chi = detail["members"][2]["id"]
    joined = await other_client.post("/join", json={"token": token, "member_id": chi})
    assert joined.status_code == 200
    await remove_member(session, detail["id"], 1)

    preview = (await client.post("/join/preview", json={"token": token})).json()

    assert [(m["display_name"], m["joined"]) for m in preview["members"]] == [
        ("An", True),
        ("Chi", True),
    ]


async def test_preview_reports_signed_out_or_expired_devices_as_not_joined(
    client: AsyncClient, other_client: AsyncClient, clock: FrozenClock
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]
    assert (
        await other_client.post("/join", json={"token": token, "member_id": binh})
    ).status_code == 200
    assert (await other_client.post("/devices/me/sign-out")).status_code == 204

    after_sign_out = (await other_client.post("/join/preview", json={"token": token})).json()
    assert [(m["display_name"], m["joined"]) for m in after_sign_out["members"]] == [
        ("An", True),
        ("Binh", False),
        ("Chi", False),
    ]

    clock.advance(timedelta(days=181))
    after_expiry = (await other_client.post("/join/preview", json={"token": token})).json()
    assert [(m["display_name"], m["joined"]) for m in after_expiry["members"]] == [
        ("An", False),
        ("Binh", False),
        ("Chi", False),
    ]


async def test_preview_of_a_locked_trip_works_and_says_so(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    await persist(
        session,
        update(Trip).where(Trip.id == uuid.UUID(detail["id"])).values(locked_at=datetime.now(UTC)),
    )

    response = await other_client.post("/join/preview", json={"token": token})

    assert response.status_code == 200
    assert response.json()["trip"]["locked"] is True


@pytest.mark.parametrize("path", ["/join/preview", "/join"])
async def test_unknown_malformed_and_rotated_tokens_get_one_404(
    app: FastAPI,
    client: AsyncClient,
    session: AsyncSession,
    settings: Settings,
    path: str,
) -> None:
    detail, old_token = await shared_trip(client)
    trip_id = uuid.UUID(detail["id"])
    new_token = derive_share_token(settings.share_link_key_bytes, trip_id, 2)
    await persist(
        session,
        update(Trip)
        .where(Trip.id == trip_id)
        .values(share_token_version=2, share_token_hash=hash_token(new_token)),
    )
    unknown = derive_share_token(settings.share_link_key_bytes, uuid.uuid4(), 1)
    choice = {"member_id": detail["members"][1]["id"]} if path == "/join" else {}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test", headers=CSRF_HEADERS
    ) as anon:
        responses = [
            await anon.post(path, json={"token": token, **choice})
            for token in [unknown, "not a token", "", old_token]
        ]
        current = await anon.post(path, json={"token": new_token, **choice})

    assert [r.status_code for r in responses] == [404] * 4
    assert all(r.json() == NOT_FOUND for r in responses)
    assert len({r.content for r in responses}) == 1
    assert all("set-cookie" not in r.headers for r in responses)
    assert current.status_code == 200


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({}, "body.token"),
        ({"token": "x" * 65}, "body.token"),
        ({"token": "x" * 60_000}, "body.token"),
        ({"token": 43}, "body.token"),
        ({"token": "a" * 43, "member_id": None}, "body.member_id"),
    ],
)
async def test_preview_rejects_invalid_bodies(
    client: AsyncClient, payload: dict[str, Any], field: str
) -> None:
    response = await client.post("/join/preview", json=payload)

    assert response.status_code == 422
    assert response.json()["fields"] == [field]
