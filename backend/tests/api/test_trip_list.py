import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import event, update
from sqlalchemy.engine.interfaces import DBAPICursor, ExecutionContext
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.repositories.models import Member, Trip
from tests.api.test_trips import body, create

pytestmark = pytest.mark.anyio

SUMMARY_KEYS = {
    "id",
    "name",
    "currency",
    "starts_on",
    "ends_on",
    "uses_fund",
    "closed",
    "member_count",
    "me",
}


async def test_second_create_reuses_the_device_and_the_list_orders_both(
    client: AsyncClient,
) -> None:
    first = await create(client, name="Early", starts_on="2026-01-10")
    second = await client.post("/trips", json=body(name="Late", starts_on="2026-06-01"))

    assert second.status_code == 201
    assert "set-cookie" not in second.headers
    listed = (await client.get("/trips")).json()["trips"]
    assert [t["id"] for t in listed] == [second.json()["id"], first["id"]]


async def test_list_without_a_cookie_is_empty_and_creates_no_device(client: AsyncClient) -> None:
    response = await client.get("/trips")

    assert response.status_code == 200
    assert response.json() == {"trips": []}
    assert "set-cookie" not in response.headers


async def test_list_item_shape_and_counts(client: AsyncClient, session: AsyncSession) -> None:
    detail = await create(client, uses_fund=True, starts_on="2026-02-01")
    await session.execute(
        update(Member)
        .where(Member.trip_id == uuid.UUID(detail["id"]), Member.position == 2)
        .values(removed_at=datetime.now(UTC))
    )

    (item,) = (await client.get("/trips")).json()["trips"]

    assert set(item) == SUMMARY_KEYS
    assert item == {
        "id": detail["id"],
        "name": "Phu Quoc",
        "currency": "VND",
        "starts_on": "2026-02-01",
        "ends_on": None,
        "uses_fund": True,
        "closed": False,
        "member_count": 2,
        "me": detail["me"],
    }


async def test_list_orders_open_trips_first_then_start_date_then_creation(
    client: AsyncClient, session: AsyncSession
) -> None:
    undated_old = await create(client, name="undated old")
    undated_new = await create(client, name="undated new")
    early = await create(client, name="early", starts_on="2026-01-01")
    late = await create(client, name="late", starts_on="2026-12-01")
    closed = await create(client, name="closed", starts_on="2027-01-01")
    for trip_id, created_at in [(undated_old["id"], 1), (undated_new["id"], 2)]:
        await session.execute(
            update(Trip)
            .where(Trip.id == uuid.UUID(trip_id))
            .values(created_at=datetime(2026, 1, created_at, tzinfo=UTC))
        )
    await session.execute(
        update(Trip).where(Trip.id == uuid.UUID(closed["id"])).values(closed_at=datetime.now(UTC))
    )

    listed = (await client.get("/trips")).json()["trips"]

    assert [t["id"] for t in listed] == [
        late["id"],
        early["id"],
        undated_new["id"],
        undated_old["id"],
        closed["id"],
    ]
    assert listed[-1]["closed"] is True


async def test_list_never_shows_another_devices_trips(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    mine = await create(client, name="mine")
    await create(other_client, name="theirs")

    listed = (await client.get("/trips")).json()["trips"]

    assert [t["id"] for t in listed] == [mine["id"]]


async def test_list_query_count_does_not_grow_with_trips(
    client: AsyncClient, db_engine: AsyncEngine
) -> None:
    statements: list[str] = []

    def record(
        conn: object,
        cursor: DBAPICursor,
        statement: str,
        parameters: object,
        context: ExecutionContext | None,
        executemany: bool,
    ) -> None:
        if not statement.startswith(("SAVEPOINT", "RELEASE")):
            statements.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", record)
    try:
        await create(client)
        statements.clear()
        await client.get("/trips")
        with_one_trip = len(statements)
        for index in range(5):
            await create(client, name=f"Trip {index}")
        statements.clear()
        await client.get("/trips")
        with_six_trips = len(statements)
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", record)

    assert with_one_trip == with_six_trips
    assert with_six_trips == 2
