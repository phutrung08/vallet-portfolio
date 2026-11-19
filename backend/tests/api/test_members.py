import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import limits
from app.repositories.models import Trip
from app.services import members
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_join import join
from tests.api.test_join_preview import persist, remove_member, shared_trip
from tests.api.test_trip_lock import TRIP_LOCKED
from tests.api.test_trips import MEMBER_KEYS, NOT_FOUND, create

pytestmark = pytest.mark.anyio

NAME_TAKEN = {"code": "name_taken", "message": "Name is already taken"}
TRIP_CLOSED = {"code": "trip_closed", "message": "Trip is closed"}


async def lock_trip(session: AsyncSession, trip_id: str) -> None:
    statement = (
        update(Trip).where(Trip.id == uuid.UUID(trip_id)).values(locked_at=datetime.now(UTC))
    )
    await persist(session, statement)


async def add(client: AsyncClient, trip_id: str, name: str) -> Response:
    return await client.post(f"/trips/{trip_id}/members", json={"display_name": name})


async def rename(client: AsyncClient, trip_id: str, member_id: str, name: str) -> Response:
    return await client.patch(f"/trips/{trip_id}/members/{member_id}", json={"display_name": name})


async def test_add_returns_the_member_at_the_next_position(client: AsyncClient) -> None:
    detail = await create(client)

    response = await add(client, detail["id"], "  Dung  ")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == MEMBER_KEYS
    assert (body["display_name"], body["position"], body["removed"]) == ("Dung", 3, False)
    members_list = (await client.get(f"/trips/{detail['id']}")).json()["members"]
    assert members_list[-1] == body


async def test_position_follows_the_highest_including_removed_members(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await remove_member(session, detail["id"], 2)

    response = await add(client, detail["id"], "Dung")

    assert response.json()["position"] == 3


@pytest.mark.parametrize(
    "name",
    ["an", "BINH", unicodedata.normalize("NFD", "Hợp"), unicodedata.normalize("NFD", "HỢP")],
)
async def test_add_with_a_taken_name_is_409(client: AsyncClient, name: str) -> None:
    detail = await create(client, member_names=["Binh", "Hợp"])

    response = await add(client, detail["id"], f"  {name} ")

    assert (response.status_code, response.json()) == (409, NAME_TAKEN)


async def test_name_of_a_removed_member_can_be_added_again(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await remove_member(session, detail["id"], 1)

    assert (await add(client, detail["id"], "binh")).status_code == 201


async def test_add_to_a_full_trip_is_409(client: AsyncClient, session: AsyncSession) -> None:
    detail = await create(client, member_names=[f"Member {i}" for i in range(49)])

    full = await add(client, detail["id"], "Dung")
    await remove_member(session, detail["id"], 10)
    after_removal = await add(client, detail["id"], "Dung")

    assert (full.status_code, full.json()) == (
        409,
        {"code": "trip_full", "message": "Trip is full"},
    )
    assert (after_removal.status_code, after_removal.json()["position"]) == (201, 50)


async def test_total_member_row_cap_blocks_add_even_after_soft_removals(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_TOTAL_MEMBERS", 4)
    detail = await create(client)
    assert (await add(client, detail["id"], "Dung")).status_code == 201
    assert (
        await client.delete(f"/trips/{detail['id']}/members/{detail['members'][1]['id']}")
    ).status_code == 204

    capped = await add(client, detail["id"], "Em")

    assert capped.status_code == 409
    assert capped.json()["code"] == "trip_full"


async def test_add_and_rename_on_locked_or_closed_trip_are_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    locked = await create(client)
    await lock_trip(session, locked["id"])
    closed = await create(client)
    await client.post(f"/trips/{closed['id']}/close")

    locked_add = await add(client, locked["id"], "Dung")
    locked_rename = await rename(client, locked["id"], locked["members"][1]["id"], "Dung")
    closed_add = await add(client, closed["id"], "Dung")
    closed_rename = await rename(client, closed["id"], closed["members"][1]["id"], "Dung")

    assert (locked_add.status_code, locked_add.json()) == (403, TRIP_LOCKED)
    assert (locked_rename.status_code, locked_rename.json()) == (403, TRIP_LOCKED)
    assert (closed_add.status_code, closed_add.json()) == (403, TRIP_CLOSED)
    assert (closed_rename.status_code, closed_rename.json()) == (403, TRIP_CLOSED)


async def test_removed_caller_before_lock_cannot_add_or_rename_or_remove(
    client: AsyncClient, session: AsyncSession, clock: FrozenClock
) -> None:
    detail = await create(client)
    trip_id = uuid.UUID(detail["id"])
    actor_id = uuid.UUID(detail["me"])
    target_id = uuid.UUID(detail["members"][1]["id"])
    await remove_member(session, detail["id"], 0)

    with pytest.raises(RuleViolation) as adding:
        await members.add_member(session, trip_id, actor_id, "Dung", clock.now)
    with pytest.raises(RuleViolation) as renaming:
        await members.rename_member(session, trip_id, actor_id, target_id, "Bao", clock.now)
    with pytest.raises(RuleViolation) as removing:
        await members.remove_member(session, trip_id, actor_id, target_id, clock.now)

    assert (adding.value.code, renaming.value.code, removing.value.code) == (
        "member_not_active",
    ) * 3


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"display_name": "Dung", "position": 0}, "body.position"),
        ({"display_name": ""}, "body.display_name"),
        ({"display_name": " \t\n "}, "body.display_name"),
        ({"display_name": "x" * 41}, "body.display_name"),
        ({}, "body.display_name"),
    ],
)
@pytest.mark.parametrize("method", ["POST", "PATCH"])
async def test_invalid_bodies_are_422(
    client: AsyncClient, method: str, payload: dict[str, Any], field: str
) -> None:
    detail = await create(client)
    suffix = "" if method == "POST" else f"/{detail['members'][1]['id']}"

    response = await client.request(method, f"/trips/{detail['id']}/members{suffix}", json=payload)

    assert response.status_code == 422
    assert response.json()["fields"] == [field]


async def test_add_is_consistent_with_join(client: AsyncClient, other_client: AsyncClient) -> None:
    detail, token = await shared_trip(client)
    await add(client, detail["id"], "Dung")

    response = await join(other_client, token, new_name="dung")

    assert (response.status_code, response.json()) == (409, NAME_TAKEN)


async def test_rename_returns_the_member(client: AsyncClient) -> None:
    detail = await create(client)
    binh = detail["members"][1]

    response = await rename(client, detail["id"], binh["id"], "  Bao ")

    assert response.status_code == 200
    assert response.json() == binh | {"display_name": "Bao"}
    members_list = (await client.get(f"/trips/{detail['id']}")).json()["members"]
    assert members_list[1] == response.json()


@pytest.mark.parametrize("name", ["Binh", "BINH", unicodedata.normalize("NFD", "Hợp")])
async def test_renaming_to_its_own_name_or_a_case_variant_is_allowed(
    client: AsyncClient, name: str
) -> None:
    detail = await create(client, member_names=["Binh", "Hợp"])
    target_idx = 2 if "Hợp" in unicodedata.normalize("NFC", name) else 1

    response = await rename(client, detail["id"], detail["members"][target_idx]["id"], name)

    assert response.status_code == 200
    assert response.json()["display_name"] == unicodedata.normalize("NFC", name)


async def test_rename_to_another_active_members_name_is_409(client: AsyncClient) -> None:
    detail = await create(client)

    response = await rename(client, detail["id"], detail["members"][1]["id"], "CHI")

    assert (response.status_code, response.json()) == (409, NAME_TAKEN)


async def test_rename_to_a_removed_members_name_is_allowed(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await remove_member(session, detail["id"], 2)

    response = await rename(client, detail["id"], detail["members"][1]["id"], "Chi")

    assert response.status_code == 200


async def test_rename_of_a_removed_or_foreign_or_unknown_member_is_404(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    foreign = (await create(other_client))["members"][1]["id"]
    await remove_member(session, detail["id"], 2)

    ids = [detail["members"][2]["id"], foreign, str(uuid.uuid4())]
    responses = [await rename(client, detail["id"], member_id, "Dung") for member_id in ids]

    assert [r.status_code for r in responses] == [404] * 3
    assert all(r.json() == NOT_FOUND for r in responses)
