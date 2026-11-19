import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.models import Member
from tests.api.test_join import join, memberships_of
from tests.api.test_join_preview import shared_trip
from tests.api.test_members import TRIP_CLOSED, TRIP_LOCKED, lock_trip
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio


async def remove(client: AsyncClient, trip_id: str, member_id: str) -> Response:
    return await client.delete(f"/trips/{trip_id}/members/{member_id}")


async def test_remove_soft_deletes_and_keeps_the_member_listed(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    chi = detail["members"][2]["id"]

    response = await remove(client, detail["id"], chi)

    assert (response.status_code, response.content) == (204, b"")
    row = await session.scalar(
        select(Member).where(Member.id == uuid.UUID(chi)).execution_options(populate_existing=True)
    )
    assert row is not None and row.removed_at is not None
    members = (await client.get(f"/trips/{detail['id']}")).json()["members"]
    assert [(m["display_name"], m["removed"]) for m in members] == [
        ("An", False),
        ("Binh", False),
        ("Chi", True),
    ]


async def test_removed_members_devices_lose_access_but_others_keep_it(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]
    await join(other_client, token, member_id=binh)

    await remove(client, detail["id"], binh)

    gone = await other_client.get(f"/trips/{detail['id']}")
    assert (gone.status_code, gone.json()) == (404, NOT_FOUND)
    assert (await other_client.get("/trips")).json() == {"trips": []}
    assert (await client.get(f"/trips/{detail['id']}")).status_code == 200
    (membership,) = await memberships_of(session, other_client, settings, detail["id"])
    assert membership.revoked_at is not None


async def test_removing_the_fund_holder_is_409(client: AsyncClient) -> None:
    detail = await create(client, uses_fund=True)

    response = await remove(client, detail["id"], detail["fund_holder_id"])

    assert (response.status_code, response.json()) == (
        409,
        {"code": "member_is_fund_holder", "message": "Member holds the fund"},
    )
    assert (await client.get(f"/trips/{detail['id']}")).status_code == 200


async def test_removing_the_last_active_member_is_409(client: AsyncClient) -> None:
    detail = await create(client)
    for member in detail["members"][1:]:
        assert (await remove(client, detail["id"], member["id"])).status_code == 204

    response = await remove(client, detail["id"], detail["me"])

    assert (response.status_code, response.json()) == (
        409,
        {"code": "last_member", "message": "Cannot remove the last member"},
    )
    assert (await client.get(f"/trips/{detail['id']}")).status_code == 200


async def test_a_member_may_remove_themselves_and_then_loses_access(client: AsyncClient) -> None:
    detail = await create(client)

    response = await remove(client, detail["id"], detail["me"])

    assert response.status_code == 204
    after = await client.get(f"/trips/{detail['id']}")
    assert (after.status_code, after.json()) == (404, NOT_FOUND)


async def test_remove_of_a_removed_foreign_or_unknown_member_is_404(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail = await create(client)
    foreign = (await create(other_client))["members"][1]["id"]
    chi = detail["members"][2]["id"]
    await remove(client, detail["id"], chi)

    ids = [chi, foreign, str(uuid.uuid4())]
    responses = [await remove(client, detail["id"], member_id) for member_id in ids]

    assert [r.status_code for r in responses] == [404] * 3
    assert all(r.json() == NOT_FOUND for r in responses)


async def test_remove_on_a_locked_or_closed_trip_is_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    locked = await create(client)
    await lock_trip(session, locked["id"])
    closed = await create(client)
    await client.post(f"/trips/{closed['id']}/close")

    locked_res = await remove(client, locked["id"], locked["members"][1]["id"])
    closed_res = await remove(client, closed["id"], closed["members"][1]["id"])

    assert (locked_res.status_code, locked_res.json()) == (403, TRIP_LOCKED)
    assert (closed_res.status_code, closed_res.json()) == (403, TRIP_CLOSED)


async def test_leave_removes_the_trip_from_this_device_only(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]
    await join(other_client, token, member_id=binh)

    response = await client.post(f"/trips/{detail['id']}/leave")

    assert (response.status_code, response.content) == (204, b"")
    gone = await client.get(f"/trips/{detail['id']}")
    assert (gone.status_code, gone.json()) == (404, NOT_FOUND)
    assert (await client.get("/trips")).json() == {"trips": []}
    still_there = await other_client.get(f"/trips/{detail['id']}")
    assert still_there.status_code == 200
    assert [m["removed"] for m in still_there.json()["members"]] == [False] * 3
    (membership,) = await memberships_of(session, client, settings, detail["id"])
    assert membership.revoked_at is not None


async def test_leave_twice_is_404_the_second_time(client: AsyncClient) -> None:
    detail = await create(client)
    await client.post(f"/trips/{detail['id']}/leave")

    again = await client.post(f"/trips/{detail['id']}/leave")

    assert (again.status_code, again.json()) == (404, NOT_FOUND)


async def test_leaving_then_rejoining_reactivates_the_same_membership(
    client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    detail, token = await shared_trip(client)
    (before,) = await memberships_of(session, client, settings, detail["id"])
    created_at = before.created_at
    await client.post(f"/trips/{detail['id']}/leave")

    response = await join(client, token, member_id=detail["me"])

    assert response.status_code == 200
    (after,) = await memberships_of(session, client, settings, detail["id"])
    assert (after.member_id, after.created_at, after.revoked_at) == (
        before.member_id,
        created_at,
        None,
    )
    assert (await client.get(f"/trips/{detail['id']}")).status_code == 200


async def test_leave_works_on_a_locked_trip(client: AsyncClient, session: AsyncSession) -> None:
    detail = await create(client)
    await lock_trip(session, detail["id"])

    assert (await client.post(f"/trips/{detail['id']}/leave")).status_code == 204
