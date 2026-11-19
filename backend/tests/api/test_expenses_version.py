import pytest
from httpx import AsyncClient

from tests.api.test_expenses_create import created, expense_body, group_trip
from tests.api.test_expenses_edit import everyone, put

pytestmark = pytest.mark.anyio

VERSION_CONFLICT = {"code": "version_conflict", "message": "Expense was changed by someone else"}


async def test_a_new_expense_is_version_1(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)

    expense = await created(client, trip_id, expense_body(ids[0], everyone(ids)))

    assert expense["version"] == 1


async def test_an_edit_of_the_current_version_bumps_it(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))

    first = await put(client, trip_id, original["id"], expense_body(ids[1], everyone(ids)), 1)
    second = await put(client, trip_id, original["id"], expense_body(ids[2], everyone(ids)), 2)

    assert (first.status_code, first.json()["version"]) == (200, 2)
    assert (second.status_code, second.json()["version"]) == (200, 3)


async def test_an_edit_of_an_old_version_is_409_and_changes_nothing(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    url = f"/trips/{trip_id}/expenses/{original['id']}"
    await put(client, trip_id, original["id"], expense_body(ids[1], everyone(ids)), 1)
    current = (await client.get(url)).json()

    stale = await put(
        client, trip_id, original["id"], expense_body(ids[2], everyone(ids), amount=1), 1
    )

    assert stale.status_code == 409
    assert stale.json() == VERSION_CONFLICT
    assert (await client.get(url)).json() == current


@pytest.mark.parametrize("version", [None, 0, "1", 1.0, True])
async def test_the_version_must_be_a_positive_integer(client: AsyncClient, version: object) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    body = expense_body(ids[0], everyone(ids))
    if version is not None:
        body["version"] = version

    response = await client.put(f"/trips/{trip_id}/expenses/{original['id']}", json=body)

    assert response.status_code == 422
    assert response.json()["fields"] == ["body.version"]


async def test_delete_needs_no_version(client: AsyncClient) -> None:
    trip_id, ids = await group_trip(client)
    original = await created(client, trip_id, expense_body(ids[0], everyone(ids)))
    await put(client, trip_id, original["id"], expense_body(ids[1], everyone(ids)), 1)

    response = await client.delete(f"/trips/{trip_id}/expenses/{original['id']}")

    assert response.status_code == 204
