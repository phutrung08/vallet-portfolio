import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event, update
from sqlalchemy.engine.interfaces import DBAPICursor, ExecutionContext
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.repositories.models import Expense
from tests.api.test_expenses_create import (
    EXPENSE_KEYS,
    created,
    expense_body,
    group_trip,
    parts,
)
from tests.api.test_join_preview import persist, remove_member
from tests.api.test_trips import NOT_FOUND

pytestmark = pytest.mark.anyio

# The device lookup and the membership lookup that every trip route starts with.
MEMBERSHIP_QUERIES = 2


def everyone(ids: list[str]) -> dict[str, Any]:
    return {"mode": "equal", "participants": ids}


async def add(
    client: AsyncClient, trip_id: str, ids: list[str], day: str, amount: int = 100_000
) -> dict[str, Any]:
    body = expense_body(ids[0], everyone(ids), spent_on=day, amount=amount)
    return await created(client, trip_id, body)


async def soft_delete(session: AsyncSession, expense_id: str) -> None:
    statement = (
        update(Expense)
        .where(Expense.id == uuid.UUID(expense_id))
        .values(deleted_at=datetime.now(UTC))
    )
    await persist(session, statement)


@contextmanager
def recorded_statements(engine: AsyncEngine) -> Iterator[list[str]]:
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

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


async def test_days_are_summed_per_day_newest_first_without_deleted(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    await add(client, trip_id, ids, "2026-11-07", 300_000)
    await add(client, trip_id, ids, "2026-11-08", 1_000_000)
    gone = await add(client, trip_id, ids, "2026-11-08", 5_000)
    await add(client, trip_id, ids, "2026-11-08", 941_000)
    await add(client, trip_id, ids, "2026-11-06", 7)
    await soft_delete(session, gone["id"])

    response = await client.get(f"/trips/{trip_id}/expenses/days")

    assert response.status_code == 200
    assert response.json() == {
        "days": [
            {"date": "2026-11-08", "count": 2, "total": 1_941_000},
            {"date": "2026-11-07", "count": 1, "total": 300_000},
            {"date": "2026-11-06", "count": 1, "total": 7},
        ]
    }


async def test_days_of_a_trip_without_expenses_is_empty(client: AsyncClient) -> None:
    trip_id, _ = await group_trip(client)

    response = await client.get(f"/trips/{trip_id}/expenses/days")

    assert (response.status_code, response.json()) == (200, {"days": []})


async def test_days_ignore_other_trips(client: AsyncClient, other_client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    other_id, other_ids = await group_trip(other_client)
    await add(client, trip_id, ids, "2026-11-07")
    await add(other_client, other_id, other_ids, "2026-11-09")

    days = (await client.get(f"/trips/{trip_id}/expenses/days")).json()["days"]

    assert [d["date"] for d in days] == ["2026-11-07"]


async def test_day_list_needs_the_day(client: AsyncClient) -> None:
    trip_id, _ = await group_trip(client)

    for query in ("", "?day=", "?day=yesterday"):
        response = await client.get(f"/trips/{trip_id}/expenses{query}")
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"


async def test_day_list_holds_that_day_only_newest_created_first(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    oldest = await add(client, trip_id, ids, "2026-11-08")
    newest = await add(client, trip_id, ids, "2026-11-08")
    middle = await add(client, trip_id, ids, "2026-11-08")
    gone = await add(client, trip_id, ids, "2026-11-08")
    await add(client, trip_id, ids, "2026-11-09")
    for expense, minute in [(oldest, 1), (middle, 2), (newest, 3), (gone, 4)]:
        statement = (
            update(Expense)
            .where(Expense.id == uuid.UUID(expense["id"]))
            .values(created_at=datetime(2026, 11, 8, 10, minute, tzinfo=UTC))
        )
        await persist(session, statement)
    await soft_delete(session, gone["id"])

    response = await client.get(f"/trips/{trip_id}/expenses", params={"day": "2026-11-08"})

    listed = response.json()["expenses"]
    assert [e["id"] for e in listed] == [newest["id"], middle["id"], oldest["id"]]
    assert all(set(e) == EXPENSE_KEYS for e in listed)


async def test_equal_creation_times_fall_back_to_id_descending(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    for _ in range(4):
        await add(client, trip_id, ids, "2026-11-08")

    listed = (await client.get(f"/trips/{trip_id}/expenses?day=2026-11-08")).json()["expenses"]

    keys = [e["id"] for e in listed]
    assert len({e["created_at"] for e in listed}) == 1
    assert keys == sorted(keys, reverse=True)


async def test_a_day_without_expenses_is_an_empty_list(client: AsyncClient) -> None:
    trip_id, _ = await group_trip(client)

    response = await client.get(f"/trips/{trip_id}/expenses?day=2026-11-08")

    assert (response.status_code, response.json()) == (200, {"expenses": []})


async def test_shares_follow_member_position_and_keep_removed_members(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    split = {"mode": "shares", "shares": {ids[4]: 1, ids[2]: 2, ids[5]: 1}}
    made = await created(client, trip_id, expense_body(ids[2], split, amount=400_000))
    await remove_member(session, trip_id, 5)

    detail = (await client.get(f"/trips/{trip_id}/expenses/{made['id']}")).json()

    assert parts(detail) == [(ids[2], 2, 200_000), (ids[4], 1, 100_000), (ids[5], 1, 100_000)]
    listed = (await client.get(f"/trips/{trip_id}/expenses?day=2026-11-07")).json()["expenses"]
    assert listed == [detail]


async def test_detail_is_the_created_expense_with_no_editor_yet(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    made = await add(client, trip_id, ids, "2026-11-07")

    response = await client.get(f"/trips/{trip_id}/expenses/{made['id']}")

    assert response.status_code == 200
    assert response.json() == made
    assert response.json()["updated_by"] is None


async def test_detail_of_deleted_foreign_and_unknown_expenses_is_the_same_404(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, ids = await group_trip(client)
    other_id, other_ids = await group_trip(other_client)
    deleted = await add(client, trip_id, ids, "2026-11-07")
    foreign = await add(other_client, other_id, other_ids, "2026-11-07")
    await soft_delete(session, deleted["id"])

    responses = [
        await client.get(f"/trips/{trip_id}/expenses/{expense_id}")
        for expense_id in (deleted["id"], foreign["id"], str(uuid.uuid4()))
    ]

    assert [r.status_code for r in responses] == [404] * 3
    assert all(r.json() == NOT_FOUND for r in responses)


async def test_day_list_uses_two_queries_however_many_expenses(
    client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await group_trip(client)
    await add(client, trip_id, ids, "2026-11-08")
    url = f"/trips/{trip_id}/expenses?day=2026-11-08"
    with recorded_statements(db_engine) as statements:
        await client.get(url)
        with_one = len(statements)
        for _ in range(5):
            await add(client, trip_id, ids, "2026-11-08")
        statements.clear()
        listed = (await client.get(url)).json()["expenses"]
        with_six = len(statements)

    assert len(listed) == 6
    assert with_one == with_six
    assert with_six == 2 + MEMBERSHIP_QUERIES


async def test_detail_and_days_query_counts(client: AsyncClient, db_engine: AsyncEngine) -> None:
    trip_id, ids = await group_trip(client)
    made = await add(client, trip_id, ids, "2026-11-08")

    with recorded_statements(db_engine) as statements:
        await client.get(f"/trips/{trip_id}/expenses/{made['id']}")
        detail = len(statements)
        statements.clear()
        await client.get(f"/trips/{trip_id}/expenses/days")
        days = len(statements)

    assert (detail, days) == (2 + MEMBERSHIP_QUERIES, 1 + MEMBERSHIP_QUERIES)
