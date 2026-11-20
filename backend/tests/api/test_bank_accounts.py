import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.crypto import DecryptionError, decrypt
from app.core.logging import configure_logging
from app.repositories.models import BankAccount
from app.services import bank_accounts
from app.services.bank_accounts import NewBankAccount, bank_account_aad
from app.services.errors import RuleViolation
from tests.api.conftest import FrozenClock
from tests.api.test_join import join
from tests.api.test_join_preview import remove_member, shared_trip
from tests.api.test_payments import TRIP_LOCKED, set_trip, trip

pytestmark = pytest.mark.anyio

NUMBER = "0123456789012"
ACCOUNT_KEYS = {
    "member_id",
    "bank_bin",
    "bank_short_name",
    "account_last4",
    "account_name",
    "updated_at",
    "bank_account_changed_at",
}


def account_body(**overrides: Any) -> dict[str, Any]:
    return {"bank_bin": "970436", "account_number": NUMBER, "account_name": "An"} | overrides


async def put_account(client: AsyncClient, trip_id: str, **overrides: Any) -> Response:
    return await client.put(
        f"/trips/{trip_id}/members/me/bank-account", json=account_body(**overrides)
    )


async def saved(client: AsyncClient, trip_id: str, **overrides: Any) -> dict[str, Any]:
    response = await put_account(client, trip_id, **overrides)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    account: dict[str, Any] = response.json()
    return account


async def listed(client: AsyncClient, trip_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"/trips/{trip_id}/bank-accounts")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"accounts"}
    accounts: list[dict[str, Any]] = response.json()["accounts"]
    return accounts


async def stored(session: AsyncSession, trip_id: str) -> list[BankAccount]:
    statement = (
        select(BankAccount)
        .where(BankAccount.trip_id == uuid.UUID(trip_id))
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(statement)).all())


async def test_setting_an_account_returns_and_lists_the_public_view(
    client: AsyncClient, clock: FrozenClock
) -> None:
    trip_id, ids = await trip(client)

    response = await put_account(client, trip_id, account_name="Nguy\u1ec5n V\u0103n \u0110\u1ee9c")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    account = response.json()
    assert set(account) == ACCOUNT_KEYS
    assert account == {
        "member_id": ids[0],
        "bank_bin": "970436",
        "bank_short_name": "Vietcombank",
        "account_last4": "9012",
        "account_name": "NGUYEN VAN DUC",
        "updated_at": account["updated_at"],
        "bank_account_changed_at": account["updated_at"],
    }
    assert datetime.fromisoformat(account["updated_at"]) == clock.now
    assert await listed(client, trip_id) == [account]
    assert NUMBER not in response.text


async def test_spaces_in_the_number_are_dropped(
    client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    trip_id, _ = await trip(client)

    account = await saved(client, trip_id, account_number=" 0123 4567 89 ")

    assert account["account_last4"] == "6789"
    (row,) = await stored(session, trip_id)
    aad = bank_account_aad(row.trip_id, row.member_id)
    assert decrypt(settings.bank_data_key_bytes, row.account_number_encrypted, aad) == "0123456789"


async def test_the_stored_number_is_ciphertext_bound_to_its_row(
    client: AsyncClient, session: AsyncSession, settings: Settings
) -> None:
    trip_id, ids = await trip(client)
    await saved(client, trip_id)

    (row,) = await stored(session, trip_id)

    assert NUMBER.encode() not in row.account_number_encrypted
    assert NUMBER[-4:].encode() not in row.account_number_encrypted
    key = settings.bank_data_key_bytes
    own_aad = bank_account_aad(row.trip_id, row.member_id)
    assert decrypt(key, row.account_number_encrypted, own_aad) == NUMBER
    with pytest.raises(DecryptionError):
        decrypt(key, row.account_number_encrypted, bank_account_aad(row.trip_id, uuid.UUID(ids[1])))


async def test_a_second_put_replaces_the_account(
    client: AsyncClient, session: AsyncSession, settings: Settings, clock: FrozenClock
) -> None:
    trip_id, _ = await trip(client)
    first = await saved(client, trip_id)
    clock.advance(timedelta(minutes=5))

    second = await saved(client, trip_id, bank_bin="970422", account_number="99998888")

    assert (second["bank_short_name"], second["account_last4"]) == ("MBBank", "8888")
    assert second["updated_at"] > first["updated_at"]
    assert await listed(client, trip_id) == [second]
    (row,) = await stored(session, trip_id)
    aad = bank_account_aad(row.trip_id, row.member_id)
    assert decrypt(settings.bank_data_key_bytes, row.account_number_encrypted, aad) == "99998888"
    assert row.created_at < row.updated_at


async def test_delete_removes_the_account_and_is_idempotent(client: AsyncClient) -> None:
    trip_id, _ = await trip(client)
    await saved(client, trip_id)

    responses = [await client.delete(f"/trips/{trip_id}/members/me/bank-account") for _ in "ab"]

    assert [r.status_code for r in responses] == [204, 204]
    assert await listed(client, trip_id) == []


async def test_a_put_always_writes_the_callers_own_row(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail, token = await shared_trip(client)
    an, binh = detail["members"][0]["id"], detail["members"][1]["id"]
    assert (await join(other_client, token, member_id=binh)).status_code == 200
    mine = await saved(client, detail["id"])

    # Extra fields are forbidden and the route has no {member_id}, preventing spoofing.
    smuggled = await put_account(other_client, detail["id"], member_id=an)
    theirs = await saved(other_client, detail["id"], account_number="55556666")
    await other_client.delete(f"/trips/{detail['id']}/members/me/bank-account")

    assert smuggled.status_code == 422
    assert theirs["member_id"] == binh
    assert await listed(client, detail["id"]) == [mine]


async def test_the_list_keeps_removed_members_in_position_order(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]
    await join(other_client, token, member_id=binh)
    theirs = await saved(other_client, detail["id"], account_name="L\u00ea B\u00ecnh")
    mine = await saved(client, detail["id"])
    await remove_member(session, detail["id"], 1)

    assert await listed(client, detail["id"]) == [mine, theirs]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"bank_bin": "123456"}, "body.bank_bin"),
        ({"bank_bin": "97043"}, "body.bank_bin"),
        ({"account_number": "01234A6789"}, "body.account_number"),
        ({"account_number": "12345"}, "body.account_number"),
        ({"account_number": "1" * 20}, "body.account_number"),
        ({"account_number": "123-456-789"}, "body.account_number"),
        ({"account_number": 123456789}, "body.account_number"),
        ({"account_name": "   "}, "body.account_name"),
        ({"account_name": "An 2"}, "body.account_name"),
        ({"account_name": "A" * 51}, "body.account_name"),
        ({"account_name": "\u6771\u4eac"}, "body.account_name"),
        ({"note": "x"}, "body.note"),
    ],
    ids=lambda value: str(value)[:30],
)
async def test_invalid_input_is_422_without_echoing_it(
    client: AsyncClient, overrides: dict[str, Any], field: str
) -> None:
    trip_id, _ = await trip(client)

    response = await put_account(client, trip_id, **overrides)

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Invalid request",
        "fields": [field],
    }
    assert await listed(client, trip_id) == []


async def test_a_locked_trip_refuses_changes(client: AsyncClient, session: AsyncSession) -> None:
    trip_id, _ = await trip(client)
    await saved(client, trip_id)
    await set_trip(session, trip_id, locked_at=datetime.now(UTC))

    put = await put_account(client, trip_id)
    deleted = await client.delete(f"/trips/{trip_id}/members/me/bank-account")

    assert [put.status_code, deleted.status_code] == [403, 403]
    assert [put.json(), deleted.json()] == [TRIP_LOCKED, TRIP_LOCKED]
    assert len(await listed(client, trip_id)) == 1


async def test_a_closed_trip_still_takes_bank_accounts(
    client: AsyncClient, session: AsyncSession
) -> None:
    trip_id, _ = await trip(client)
    await set_trip(session, trip_id, closed_at=datetime.now(UTC))

    await saved(client, trip_id)
    deleted = await client.delete(f"/trips/{trip_id}/members/me/bank-account")

    assert deleted.status_code == 204


async def test_the_account_number_never_reaches_the_logs(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    configure_logging()
    trip_id, _ = await trip(client)

    await saved(client, trip_id)
    await put_account(client, trip_id, account_number=NUMBER + "X")
    await listed(client, trip_id)

    assert NUMBER not in caplog.text


async def test_banks_are_public_and_cacheable(client: AsyncClient) -> None:
    response = await client.get("/banks")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert "set-cookie" not in response.headers
    banks = response.json()["banks"]
    assert len(banks) == 48
    assert all(set(bank) == {"bin", "code", "short_name"} for bank in banks)
    assert {"bin": "970436", "code": "VCB", "short_name": "Vietcombank"} in banks


async def test_removed_caller_is_refused_by_bank_account_services_after_lock(
    client: AsyncClient, session: AsyncSession, settings: Settings, clock: FrozenClock
) -> None:
    trip_id, ids = await trip(client)
    await remove_member(session, trip_id, 1)

    with pytest.raises(RuleViolation) as set_err:
        await bank_accounts.set_own_bank_account(
            session,
            settings.bank_data_key_bytes,
            uuid.UUID(trip_id),
            uuid.UUID(ids[1]),
            NewBankAccount("970436", NUMBER, "BINH"),
            clock.now,
        )
    with pytest.raises(RuleViolation) as del_err:
        await bank_accounts.delete_own_bank_account(
            session, uuid.UUID(trip_id), uuid.UUID(ids[1]), clock.now
        )

    assert (set_err.value.code, del_err.value.code) == ("member_not_active",) * 2
