import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import TripEvent
from tests.api.conftest import FrozenClock
from tests.api.test_bank_accounts import NUMBER, listed, put_account, saved
from tests.api.test_join import join
from tests.api.test_join_preview import shared_trip
from tests.api.test_trips import NOT_FOUND, create

pytestmark = pytest.mark.anyio

EVENT_KEYS = {"id", "kind", "actor_id", "subject_id", "created_at"}


async def events_of(client: AsyncClient, trip_id: str, **query: Any) -> dict[str, Any]:
    response = await client.get(f"/trips/{trip_id}/events", params=query)
    assert response.status_code == 200, response.text
    page: dict[str, Any] = response.json()
    assert set(page) == {"events", "next_before"}
    return page


async def kinds_of(client: AsyncClient, trip_id: str) -> list[str]:
    """Return event kinds oldest-first matching the chronological action order."""
    page = await events_of(client, trip_id, limit=100)
    return [e["kind"] for e in reversed(page["events"])]


async def step(clock: FrozenClock, response: Response) -> None:
    assert response.status_code < 300, response.text
    clock.advance(timedelta(seconds=1))


async def test_every_action_writes_its_event_with_actor_and_subject(
    client: AsyncClient, other_client: AsyncClient, clock: FrozenClock
) -> None:
    detail, token = await shared_trip(client)
    trip_id = detail["id"]
    an, binh = detail["members"][0]["id"], detail["members"][1]["id"]
    await step(clock, await join(other_client, token, member_id=binh))
    added = await client.post(f"/trips/{trip_id}/members", json={"display_name": "Dung"})
    await step(clock, added)
    dung = added.json()["id"]
    await step(
        clock, await client.patch(f"/trips/{trip_id}/members/{dung}", json={"display_name": "Dat"})
    )
    await step(clock, await client.delete(f"/trips/{trip_id}/members/{dung}"))
    await step(clock, await put_account(client, trip_id))
    await step(clock, await client.delete(f"/trips/{trip_id}/members/me/bank-account"))
    await step(clock, await client.put(f"/trips/{trip_id}/fund", json={"holder_id": an}))
    await step(clock, await client.put(f"/trips/{trip_id}/fund", json={"holder_id": None}))
    await step(clock, await client.post(f"/trips/{trip_id}/share-link/rotate"))
    await step(clock, await client.post(f"/trips/{trip_id}/lock"))
    await step(clock, await client.post(f"/trips/{trip_id}/unlock"))
    await step(clock, await client.post(f"/trips/{trip_id}/close"))
    await step(clock, await client.post(f"/trips/{trip_id}/reopen"))
    await step(clock, await other_client.post(f"/trips/{trip_id}/leave"))

    page = await events_of(client, trip_id)

    assert page["next_before"] is None
    assert all(set(e) == EVENT_KEYS for e in page["events"])
    assert [(e["kind"], e["actor_id"], e["subject_id"]) for e in reversed(page["events"])] == [
        ("member_joined", binh, binh),
        ("member_added", an, dung),
        ("member_renamed", an, dung),
        ("member_removed", an, dung),
        ("bank_account_set", an, an),
        ("bank_account_removed", an, an),
        ("fund_holder_changed", an, an),
        ("fund_holder_changed", an, None),
        ("share_link_rotated", an, None),
        ("trip_locked", an, None),
        ("trip_unlocked", an, None),
        ("trip_closed", an, None),
        ("trip_reopened", an, None),
        ("member_left", binh, binh),
    ]


async def test_rejoining_after_leaving_is_logged_again_but_repeating_a_join_is_not(
    client: AsyncClient, other_client: AsyncClient, clock: FrozenClock
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]

    for _ in range(2):
        await step(clock, await join(other_client, token, member_id=binh))
    await step(clock, await other_client.post(f"/trips/{detail['id']}/leave"))
    await step(clock, await join(other_client, token, member_id=binh))

    assert await kinds_of(client, detail["id"]) == ["member_joined", "member_left", "member_joined"]


async def test_joining_with_a_new_name_logs_one_event_for_the_new_member(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail, token = await shared_trip(client)

    joined = await join(other_client, token, new_name="Dung")

    new_id = joined.json()["me"]
    (event,) = (await events_of(client, detail["id"]))["events"]
    assert (event["kind"], event["actor_id"], event["subject_id"]) == (
        "member_joined",
        new_id,
        new_id,
    )


async def test_changes_that_change_nothing_are_not_logged(client: AsyncClient) -> None:
    trip_id = (await create(client))["id"]

    await client.delete(f"/trips/{trip_id}/members/me/bank-account")
    await client.post(f"/trips/{trip_id}/reopen")
    await client.post(f"/trips/{trip_id}/unlock")
    await client.post(f"/trips/{trip_id}/close")
    await client.post(f"/trips/{trip_id}/close")
    await client.post(f"/trips/{trip_id}/lock")
    await client.post(f"/trips/{trip_id}/lock")

    # Events share the frozen timestamp, so ordering between them is undefined.
    assert sorted(await kinds_of(client, trip_id)) == ["trip_closed", "trip_locked"]


async def test_a_refused_change_leaves_no_event(client: AsyncClient) -> None:
    trip_id = (await create(client))["id"]
    await client.post(f"/trips/{trip_id}/lock")

    refused = [
        await client.post(f"/trips/{trip_id}/members", json={"display_name": "Dung"}),
        await put_account(client, trip_id),
        await client.post(f"/trips/{trip_id}/close"),
    ]

    assert [r.status_code for r in refused] == [403, 403, 403]
    assert await kinds_of(client, trip_id) == ["trip_locked"]


async def test_expense_changes_are_not_logged(client: AsyncClient) -> None:
    trip_id = (await create(client))["id"]
    members = (await client.get(f"/trips/{trip_id}")).json()["members"]
    ids = [m["id"] for m in members]
    expense = {
        "title": "Coffee",
        "amount": 50_000,
        "category": "food",
        "spent_on": "2026-11-07",
        "paid_by": ids[0],
        "split": {"mode": "equal", "participants": ids},
    }

    assert (await client.post(f"/trips/{trip_id}/expenses", json=expense)).status_code == 201

    assert await kinds_of(client, trip_id) == []


async def test_pages_run_newest_first_and_chain_through_next_before(
    client: AsyncClient, clock: FrozenClock
) -> None:
    trip_id = (await create(client))["id"]
    for _ in range(2):
        await step(clock, await client.post(f"/trips/{trip_id}/lock"))
        await step(clock, await client.post(f"/trips/{trip_id}/unlock"))
        await step(clock, await client.post(f"/trips/{trip_id}/close"))
        await step(clock, await client.post(f"/trips/{trip_id}/reopen"))
    everything = (await events_of(client, trip_id))["events"]
    assert len(everything) == 8

    first = await events_of(client, trip_id, limit=3)
    second = await events_of(client, trip_id, limit=3, before=first["next_before"])
    third = await events_of(client, trip_id, limit=3, before=second["next_before"])

    assert [e["id"] for e in first["events"] + second["events"] + third["events"]] == [
        e["id"] for e in everything
    ]
    assert [len(p["events"]) for p in (first, second, third)] == [3, 3, 2]
    assert [p["next_before"] for p in (first, second, third)][2] is None
    assert first["next_before"] == first["events"][-1]["id"]
    stamps = [e["created_at"] for e in everything]
    assert stamps == sorted(stamps, reverse=True)
    assert everything[0]["kind"] == "trip_reopened"


async def test_events_at_the_same_instant_still_page_without_gaps_or_repeats(
    client: AsyncClient,
) -> None:
    trip_id = (await create(client))["id"]
    for _ in range(3):
        await client.post(f"/trips/{trip_id}/lock")
        await client.post(f"/trips/{trip_id}/unlock")

    seen: list[str] = []
    cursor: str | None = None
    while True:
        query = {"limit": 2} | ({} if cursor is None else {"before": cursor})
        page = await events_of(client, trip_id, **query)
        seen += [e["id"] for e in page["events"]]
        cursor = page["next_before"]
        if cursor is None:
            break

    assert len(seen) == 6
    assert len(set(seen)) == 6


async def test_the_default_page_is_fifty_and_the_limit_is_capped_at_a_hundred(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    trip_id, me = uuid.UUID(detail["id"]), uuid.UUID(detail["me"])
    session.add_all(
        TripEvent(trip_id=trip_id, actor_member_id=me, kind="trip_locked") for _ in range(120)
    )
    await session.commit()

    default = await events_of(client, detail["id"])
    biggest = await events_of(client, detail["id"], limit=100)
    too_many = await client.get(f"/trips/{trip_id}/events", params={"limit": 101})
    none = await client.get(f"/trips/{trip_id}/events", params={"limit": 0})
    bad_cursor = await client.get(f"/trips/{trip_id}/events", params={"before": "x"})

    assert (len(default["events"]), len(biggest["events"])) == (50, 100)
    assert default["next_before"] is not None
    assert [r.status_code for r in (too_many, none, bad_cursor)] == [422, 422, 422]


async def test_a_cursor_from_another_trip_or_unknown_matches_nothing(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    mine = (await create(client))["id"]
    theirs = (await create(other_client))["id"]
    await client.post(f"/trips/{mine}/lock")
    await other_client.post(f"/trips/{theirs}/lock")
    foreign = (await events_of(other_client, theirs))["events"][0]["id"]

    with_foreign = await events_of(client, mine, before=foreign)
    with_unknown = await events_of(client, mine, before=str(uuid.uuid4()))

    assert with_foreign == with_unknown == {"events": [], "next_before": None}


async def test_a_trip_reads_only_its_own_events(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    mine = (await create(client))["id"]
    theirs = (await create(other_client))["id"]
    await client.post(f"/trips/{mine}/lock")

    assert await kinds_of(client, mine) == ["trip_locked"]
    assert await kinds_of(other_client, theirs) == []


async def test_outsiders_get_404(client: AsyncClient, other_client: AsyncClient) -> None:
    trip_id = (await create(client))["id"]
    await create(other_client)

    response = await other_client.get(f"/trips/{trip_id}/events")

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


async def test_no_account_number_reaches_an_event_row_or_the_events_response(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    trip_id = detail["id"]
    await saved(client, trip_id)
    await saved(client, trip_id, account_number="99998888")
    await client.delete(f"/trips/{trip_id}/members/me/bank-account")

    response = await client.get(f"/trips/{trip_id}/events")
    rows = (
        await session.scalars(select(TripEvent).execution_options(populate_existing=True))
    ).all()

    assert len(rows) == 3
    haystack = response.text + " ".join(repr(vars(row)) for row in rows)
    for secret in (NUMBER, "99998888", "9012", "8888", "970436", "Vietcombank"):
        assert secret not in haystack
    assert {c.name for c in TripEvent.__table__.columns} == {
        "id",
        "trip_id",
        "actor_member_id",
        "subject_member_id",
        "kind",
        "created_at",
    }


async def test_bank_account_changed_at_follows_each_change(
    client: AsyncClient, clock: FrozenClock
) -> None:
    detail = await create(client)
    trip_id = detail["id"]
    first = await saved(client, trip_id)
    clock.advance(timedelta(minutes=5))
    second = await saved(client, trip_id, account_number="99998888")

    (account,) = await listed(client, trip_id)

    assert first["bank_account_changed_at"] == first["updated_at"]
    assert second["bank_account_changed_at"] > first["bank_account_changed_at"]
    assert account["bank_account_changed_at"] == second["bank_account_changed_at"]
    assert account == second
    events = (await events_of(client, trip_id))["events"]
    assert events[0]["created_at"] == account["bank_account_changed_at"]


async def test_bank_account_changed_at_is_null_without_a_logged_change(
    client: AsyncClient, session: AsyncSession
) -> None:
    detail = await create(client)
    await saved(client, detail["id"])
    for event in (await session.scalars(select(TripEvent))).all():
        await session.delete(event)
    await session.commit()

    (account,) = await listed(client, detail["id"])

    assert account["bank_account_changed_at"] is None
