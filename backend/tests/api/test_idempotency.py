import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import IdempotencyKey, Membership, TripEvent
from tests.db.factories import add_trip

pytestmark = pytest.mark.anyio

IDEMPOTENCY_CONFLICT = {
    "code": "idempotency_conflict",
    "message": "Idempotency key was used for another request",
}


async def register_member_device(
    client: AsyncClient, session: AsyncSession, trip_id: uuid.UUID, member_id: uuid.UUID
) -> uuid.UUID:
    response = await client.post("/_test/device")
    assert response.status_code == 200
    device_id = uuid.UUID(response.json()["device_id"])
    session.add(Membership(device_id=device_id, trip_id=trip_id, member_id=member_id))
    await session.commit()
    return device_id


async def post_idempotent(
    client: AsyncClient,
    trip_id: uuid.UUID,
    route: str,
    body: dict[str, object],
    key: object | None = None,
) -> Response:
    headers = {} if key is None else {"Idempotency-Key": str(key)}
    return await client.post(f"/_test/trips/{trip_id}/{route}", json=body, headers=headers)


async def event_count(session: AsyncSession, trip_id: uuid.UUID) -> int:
    statement = select(func.count()).select_from(TripEvent).where(TripEvent.trip_id == trip_id)
    return int(await session.scalar(statement) or 0)


async def test_a_retry_replays_the_first_response_and_writes_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await register_member_device(client, session, trip_id, an_id)
    key = uuid.uuid4()
    body: dict[str, object] = {"amount": 100_000}

    first = await post_idempotent(client, trip_id, "idempotent-a", body, key)
    retry = await post_idempotent(client, trip_id, "idempotent-a", body, key)

    assert (first.status_code, retry.status_code) == (201, 201)
    assert retry.json() == first.json()
    assert "idempotent-replayed" not in first.headers
    assert retry.headers["idempotent-replayed"] == "true"
    assert await event_count(session, trip_id) == 1
    stored = await session.scalar(select(IdempotencyKey).where(IdempotencyKey.key == key))
    assert stored is not None
    assert stored.route == "POST /_test/trips/{trip_id}/idempotent-a"
    assert stored.status_code == 201
    assert stored.response_body == first.json()


async def test_without_a_key_each_post_writes(client: AsyncClient, session: AsyncSession) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await register_member_device(client, session, trip_id, an_id)
    body: dict[str, object] = {"amount": 50_000}

    responses = [await post_idempotent(client, trip_id, "idempotent-a", body) for _ in range(2)]

    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json()["record_id"] != responses[1].json()["record_id"]
    assert await event_count(session, trip_id) == 2


async def test_the_same_key_with_another_body_is_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await register_member_device(client, session, trip_id, an_id)
    key = uuid.uuid4()
    await post_idempotent(client, trip_id, "idempotent-a", {"amount": 100_000}, key)

    response = await post_idempotent(client, trip_id, "idempotent-a", {"amount": 70_000}, key)

    assert response.status_code == 409
    assert response.json() == IDEMPOTENCY_CONFLICT
    assert await event_count(session, trip_id) == 1


async def test_the_same_key_on_another_route_is_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await register_member_device(client, session, trip_id, an_id)
    key = uuid.uuid4()
    await post_idempotent(client, trip_id, "idempotent-a", {"amount": 100_000}, key)

    response = await post_idempotent(client, trip_id, "idempotent-b", {"amount": 100_000}, key)

    assert response.status_code == 409
    assert response.json() == IDEMPOTENCY_CONFLICT
    assert await event_count(session, trip_id) == 1


async def test_the_same_key_in_another_trip_is_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    first_trip, (first_an, _) = await add_trip(session)
    second_trip, (second_an, _) = await add_trip(session)
    first_id, second_id = first_trip.id, second_trip.id
    await register_member_device(client, session, first_id, first_an.id)
    await register_member_device(client, session, second_id, second_an.id)
    key = uuid.uuid4()
    await post_idempotent(client, first_id, "idempotent-a", {"amount": 100_000}, key)

    response = await post_idempotent(client, second_id, "idempotent-a", {"amount": 100_000}, key)

    assert response.status_code == 409
    assert response.json() == IDEMPOTENCY_CONFLICT
    assert await event_count(session, second_id) == 0


async def test_another_device_with_the_same_key_writes_its_own(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    trip, (an, binh) = await add_trip(session)
    trip_id, an_id, binh_id = trip.id, an.id, binh.id
    await register_member_device(client, session, trip_id, an_id)
    await register_member_device(other_client, session, trip_id, binh_id)
    key = uuid.uuid4()
    body: dict[str, object] = {"amount": 100_000}

    mine = await post_idempotent(client, trip_id, "idempotent-a", body, key)
    theirs = await post_idempotent(other_client, trip_id, "idempotent-a", body, key)

    assert (mine.status_code, theirs.status_code) == (201, 201)
    assert "idempotent-replayed" not in theirs.headers
    assert mine.json()["record_id"] != theirs.json()["record_id"]
    assert mine.json()["created_by"] == str(an_id)
    assert theirs.json()["created_by"] == str(binh_id)
    assert await event_count(session, trip_id) == 2


async def test_a_refused_first_request_does_not_use_up_the_key(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await register_member_device(client, session, trip_id, an_id)
    key = uuid.uuid4()

    refused = await post_idempotent(
        client, trip_id, "idempotent-a", {"amount": 100_000, "fail_rule": True}, key
    )
    retry = await post_idempotent(
        client, trip_id, "idempotent-a", {"amount": 100_000, "fail_rule": False}, key
    )

    assert refused.status_code == 403
    assert retry.status_code == 201
    assert "idempotent-replayed" not in retry.headers
    assert await event_count(session, trip_id) == 1


@pytest.mark.parametrize("key", ["not-a-uuid", "", "1234"])
async def test_a_key_that_is_not_a_uuid_is_422(
    client: AsyncClient, session: AsyncSession, key: str
) -> None:
    trip, (an, _) = await add_trip(session)
    trip_id, an_id = trip.id, an.id
    await register_member_device(client, session, trip_id, an_id)

    response = await post_idempotent(client, trip_id, "idempotent-a", {"amount": 100_000}, key)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["fields"] == ["header.idempotency-key"]
    assert await event_count(session, trip_id) == 0
