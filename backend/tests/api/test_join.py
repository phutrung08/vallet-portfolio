import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.join import JoinPreviewRequest, JoinRequest
from app.core import limits
from app.core.config import Settings
from app.core.security import hash_token
from app.repositories.models import Device, Member, Membership, Trip
from tests.api.conftest import FrozenClock
from tests.api.test_device_session import device_cookie
from tests.api.test_join_preview import persist, remove_member, shared_trip
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio


async def join(client: AsyncClient, token: str, **choice: Any) -> Response:
    return await client.post("/join", json={"token": token, **choice})


async def memberships_of(
    session: AsyncSession, client: AsyncClient, settings: Settings, trip_id: str
) -> list[Membership]:
    token_hash = hash_token(client.cookies[settings.device_cookie_name])
    statement = (
        select(Membership)
        .join(Device, Device.id == Membership.device_id)
        .where(Device.token_hash == token_hash, Membership.trip_id == uuid.UUID(trip_id))
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(statement)).all())


async def test_join_as_an_existing_member_sets_the_cookie_and_returns_the_detail(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]

    response = await join(other_client, token, member_id=binh)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert device_cookie(response, settings).value
    assert response.json() == detail | {"me": binh}
    assert response.json() == (await other_client.get(f"/trips/{detail['id']}")).json()
    (membership,) = await memberships_of(session, other_client, settings, detail["id"])
    assert str(membership.member_id) == binh
    listed = (await other_client.get("/trips")).json()["trips"]
    assert [(t["id"], t["me"]) for t in listed] == [(detail["id"], binh)]


async def test_join_with_a_new_name_adds_a_member_at_the_next_position(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    await remove_member(session, detail["id"], 2)

    response = await join(other_client, token, new_name="  Dung  ")

    assert response.status_code == 200
    members = response.json()["members"]
    assert [(m["display_name"], m["position"], m["removed"]) for m in members] == [
        ("An", 0, False),
        ("Binh", 1, False),
        ("Chi", 2, True),
        ("Dung", 3, False),
    ]
    assert response.json()["me"] == members[3]["id"]


@pytest.mark.parametrize(
    "new_name",
    ["an", "BINH", unicodedata.normalize("NFD", "Hợp"), unicodedata.normalize("NFD", "HỢP")],
)
async def test_new_name_colliding_with_an_active_member_is_409(
    client: AsyncClient, other_client: AsyncClient, new_name: str
) -> None:
    _, token = await shared_trip(client, member_names=["Binh", "Hợp"])

    response = await join(other_client, token, new_name=f"  {new_name} ")

    assert response.status_code == 409
    assert response.json() == {"code": "name_taken", "message": "Name is already taken"}
    assert "set-cookie" not in response.headers


async def test_name_of_a_removed_member_can_be_taken_again(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    await remove_member(session, detail["id"], 1)

    response = await join(other_client, token, new_name="binh")

    assert response.status_code == 200
    assert response.json()["members"][-1]["position"] == 3


async def test_fifty_active_members_is_full(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client, member_names=[f"Member {i}" for i in range(49)])

    full = await join(other_client, token, new_name="Dung")
    await remove_member(session, detail["id"], 10)
    after_removal = await join(other_client, token, new_name="Dung")

    assert full.status_code == 409
    assert full.json() == {"code": "trip_full", "message": "Trip is full"}
    assert after_removal.status_code == 200
    assert after_removal.json()["members"][-1]["position"] == 50


async def test_revoked_membership_is_reactivated_in_place(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail, token = await shared_trip(client)
    chi = detail["members"][2]["id"]
    await join(other_client, token, member_id=chi)
    await persist(
        session,
        update(Membership)
        .where(Membership.trip_id == uuid.UUID(detail["id"]), Membership.member_id == chi)
        .values(revoked_at=datetime.now(UTC)),
    )
    assert (await other_client.get(f"/trips/{detail['id']}")).status_code == 404

    response = await join(other_client, token, member_id=chi)

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    (membership,) = await memberships_of(session, other_client, settings, detail["id"])
    assert (str(membership.member_id), membership.revoked_at) == (chi, None)


async def test_device_can_switch_to_another_unjoined_member(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail, token = await shared_trip(client)
    binh, chi = detail["members"][1]["id"], detail["members"][2]["id"]
    await join(other_client, token, member_id=binh)

    response = await join(other_client, token, member_id=chi)

    assert response.json()["me"] == chi
    (membership,) = await memberships_of(session, other_client, settings, detail["id"])
    assert str(membership.member_id) == chi


async def test_active_member_slot_cannot_be_claimed_by_another_device(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail, token = await shared_trip(client)

    hijack = await join(other_client, token, member_id=detail["me"])
    rejoin_self = await join(client, token, member_id=detail["me"])

    assert hijack.status_code == 409
    assert hijack.json()["code"] == "member_already_joined"
    assert (await other_client.get(f"/trips/{detail['id']}")).status_code == 404
    assert rejoin_self.status_code == 200
    assert rejoin_self.json()["me"] == detail["me"]


async def test_member_slot_can_be_reclaimed_after_sign_out_or_expiry(
    client: AsyncClient, other_client: AsyncClient, clock: FrozenClock
) -> None:
    detail, token = await shared_trip(client)
    creator_id = detail["me"]
    assert (await client.post("/devices/me/sign-out")).status_code == 204

    reclaimed = await join(other_client, token, member_id=creator_id)
    assert reclaimed.status_code == 200
    assert reclaimed.json()["me"] == creator_id

    clock.advance(timedelta(days=181))
    reclaimed_after_expiry = await join(client, token, member_id=creator_id)
    assert reclaimed_after_expiry.status_code == 200
    assert reclaimed_after_expiry.json()["me"] == creator_id


async def test_member_of_another_trip_or_a_removed_member_is_the_same_404(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    foreign = (await create(client))["members"][1]["id"]
    await remove_member(session, detail["id"], 1)

    responses = [
        await join(other_client, token, member_id=member_id)
        for member_id in [foreign, detail["members"][1]["id"], str(uuid.uuid4())]
    ]

    assert [r.status_code for r in responses] == [404] * 3
    assert all(r.json() == NOT_FOUND for r in responses)
    assert all("set-cookie" not in r.headers for r in responses)


async def test_locked_trip_refuses_join_and_closed_trip_refuses_new_name_only(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    locked, locked_token = await shared_trip(client)
    closed, closed_token = await shared_trip(client)
    now = datetime.now(UTC)
    await persist(
        session, update(Trip).where(Trip.id == uuid.UUID(locked["id"])).values(locked_at=now)
    )
    await persist(
        session, update(Trip).where(Trip.id == uuid.UUID(closed["id"])).values(closed_at=now)
    )

    refused_locked = await join(other_client, locked_token, new_name="Dung")
    refused_closed_new = await join(other_client, closed_token, new_name="Dung")
    accepted_closed = await join(other_client, closed_token, member_id=closed["members"][1]["id"])

    assert (refused_locked.status_code, refused_locked.json()["code"]) == (403, "trip_locked")
    assert (refused_closed_new.status_code, refused_closed_new.json()["code"]) == (
        403,
        "trip_closed",
    )
    assert await session.scalar(select(Member).where(Member.display_name == "Dung")) is None
    assert accepted_closed.status_code == 200
    assert accepted_closed.json()["closed"] is True


async def test_device_trip_cap_blocks_joining_new_trip(
    client: AsyncClient, other_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, first_token = await shared_trip(client, name="Trip 1")
    second, second_token = await shared_trip(client, name="Trip 2")
    monkeypatch.setattr(limits, "MAX_TRIPS_PER_DEVICE", 1)
    assert (await join(other_client, first_token, new_name="Guest")).status_code == 200

    capped = await join(other_client, second_token, member_id=second["members"][1]["id"])

    assert capped.status_code == 409
    assert capped.json()["code"] == "device_trip_limit_reached"


def test_share_token_is_omitted_from_schema_repr() -> None:
    secret_token = "a" * 43
    preview_req = JoinPreviewRequest(token=secret_token)
    join_req = JoinRequest(token=secret_token, new_name="Dung")

    assert secret_token not in repr(preview_req)
    assert secret_token not in repr(join_req)


@pytest.mark.parametrize(
    ("choice", "field"),
    [
        ({}, "body"),
        ({"member_id": str(uuid.uuid4()), "new_name": "Dung"}, "body"),
        ({"member_id": None, "new_name": None}, "body"),
        ({"new_name": "   "}, "body.new_name"),
        ({"new_name": "x" * 41}, "body.new_name"),
        ({"member_id": "not-a-uuid"}, "body.member_id"),
        ({"new_name": "Dung", "position": 0}, "body.position"),
    ],
)
async def test_join_rejects_invalid_bodies(
    client: AsyncClient, other_client: AsyncClient, choice: dict[str, Any], field: str
) -> None:
    _, token = await shared_trip(client)

    response = await join(other_client, token, **choice)

    assert response.status_code == 422
    assert response.json()["fields"] == [field]
    assert "set-cookie" not in response.headers


async def test_oversized_token_is_rejected_by_validation(other_client: AsyncClient) -> None:
    response = await join(other_client, "x" * 60_000, new_name="Dung")

    assert response.status_code == 422
    assert response.json()["fields"] == ["body.token"]
