import logging
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.vietqr import MAX_AMOUNT, crc16_ccitt_false
from app.repositories.models import BankAccount
from tests.api.conftest import CSRF_HEADERS
from tests.api.test_bank_accounts import saved
from tests.api.test_expenses_read import MEMBERSHIP_QUERIES, recorded_statements
from tests.api.test_join import join
from tests.api.test_join_preview import persist, remove_member, shared_trip
from tests.api.test_payments import NOT_ACTIVE, trip
from tests.api.test_trips import create
from tests.domain.test_vietqr import parse_tlv

pytestmark = pytest.mark.anyio

NO_BANK_ACCOUNT = {"code": "no_bank_account", "message": "Member has no bank account"}
NUMBER = "0123456789012"


async def qr(client: AsyncClient, trip_id: str, payee: str, amount: Any = 2_409_918) -> Response:
    return await client.get(f"/trips/{trip_id}/vietqr", params={"payee": payee, "amount": amount})


async def test_the_payload_carries_the_payees_account_and_amount(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)
    await saved(client, trip_id, account_number=NUMBER, account_name="Nguy\u1ec5n V\u0103n An")

    response = await qr(client, trip_id, ids[0])

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert {k: v for k, v in body.items() if k != "payload"} == {
        "bank_bin": "970436",
        "bank_short_name": "Vietcombank",
        "account_name": "NGUYEN VAN AN",
        "account_last4": "9012",
        "amount": 2_409_918,
        "message": "VL Phu Quoc",
    }
    payload = body["payload"]
    root = parse_tlv(payload)
    assert root["54"] == "2409918"
    assert parse_tlv(parse_tlv(root["38"])["01"]) == {"00": "970436", "01": NUMBER}
    assert parse_tlv(root["62"]) == {"08": "VL Phu Quoc"}
    assert f"{crc16_ccitt_false(payload[:-4].encode()):04X}" == root["63"]


async def test_any_member_may_show_the_qr_for_any_payee(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    detail, token = await shared_trip(client)
    an, binh = detail["members"][0]["id"], detail["members"][1]["id"]
    await join(other_client, token, member_id=binh)
    await saved(client, detail["id"])

    response = await qr(other_client, detail["id"], an)

    assert response.status_code == 200


async def test_a_removed_payee_with_an_account_still_gets_paid(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession
) -> None:
    detail, token = await shared_trip(client)
    binh = detail["members"][1]["id"]
    await join(other_client, token, member_id=binh)
    await saved(other_client, detail["id"], account_name="L\u00ea B\u00ecnh")
    await remove_member(session, detail["id"], 1)

    response = await qr(client, detail["id"], binh)

    assert response.status_code == 200
    assert response.json()["account_name"] == "LE BINH"


async def test_a_payee_without_an_account_is_409(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)

    response = await qr(client, trip_id, ids[1])

    assert response.status_code == 409
    assert response.json() == NO_BANK_ACCOUNT


async def test_an_outsider_payee_gets_the_usual_member_not_active(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    trip_id, _ = await trip(client)
    other_id, other_ids = await trip(other_client)
    await saved(other_client, other_id)

    responses = [await qr(client, trip_id, payee) for payee in (other_ids[0], str(uuid.uuid4()))]

    assert [r.status_code for r in responses] == [409, 409]
    assert [r.json() for r in responses] == [NOT_ACTIVE, NOT_ACTIVE]


async def test_a_usd_trip_has_no_vietqr(client: AsyncClient) -> None:
    detail = await create(client, currency="USD")
    await saved(client, detail["id"])

    response = await qr(client, detail["id"], detail["members"][0]["id"])

    assert response.status_code == 409
    assert response.json() == {
        "code": "currency_not_supported",
        "message": "VietQR needs a VND trip",
    }


@pytest.mark.parametrize("amount", [0, -1, MAX_AMOUNT + 1, "1.5", "abc"])
async def test_amount_out_of_range_is_422(client: AsyncClient, amount: Any) -> None:
    trip_id, ids = await trip(client)
    await saved(client, trip_id)

    response = await qr(client, trip_id, ids[0], amount)

    assert response.status_code == 422
    assert response.json()["fields"] == ["query.amount"]


async def test_the_largest_amount_is_accepted(client: AsyncClient) -> None:
    trip_id, ids = await trip(client)
    await saved(client, trip_id)

    response = await qr(client, trip_id, ids[0], MAX_AMOUNT)

    assert response.status_code == 200
    assert parse_tlv(response.json()["payload"])["54"] == str(MAX_AMOUNT)


async def test_corrupted_ciphertext_returns_500_without_leaking_ids(
    app: FastAPI,
    client: AsyncClient,
    session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    trip_id, ids = await trip(client)
    await saved(client, trip_id)
    await persist(
        session,
        update(BankAccount)
        .where(
            BankAccount.trip_id == uuid.UUID(trip_id), BankAccount.member_id == uuid.UUID(ids[0])
        )
        .values(account_number_encrypted=b"\x01" + b"\x00" * 32),
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(
        transport=transport,
        base_url="https://test",
        cookies=client.cookies,
        headers=CSRF_HEADERS,
    ) as tolerant:
        response = await tolerant.get(
            f"/trips/{trip_id}/vietqr", params={"payee": ids[0], "amount": 50_000}
        )

    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "message": "Internal server error"}
    logged = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("VietQR payload" in message for message in logged)
    assert all(ids[0] not in message and NUMBER not in message for message in logged)


async def test_vietqr_uses_single_row_member_lookup_with_constant_queries(
    client: AsyncClient, db_engine: AsyncEngine
) -> None:
    trip_id, ids = await trip(client)
    await saved(client, trip_id)

    with recorded_statements(db_engine) as statements:
        response = await qr(client, trip_id, ids[0], 50_000)

    assert response.status_code == 200
    # TripMember checks (2) + find_trip/find_member/find_bank_account (at most 3).
    assert len(statements) <= MEMBERSHIP_QUERIES + 3
