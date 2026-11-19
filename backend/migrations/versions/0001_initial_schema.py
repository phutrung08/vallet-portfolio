"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATEGORIES = "('food', 'transport', 'lodging', 'activity', 'shopping', 'other')"
_SPLIT_MODES = "('equal', 'shares', 'percent', 'exact')"
_EVENT_KINDS = (
    "('bank_account_set', 'bank_account_removed', 'fund_holder_changed', 'member_added', "
    "'member_renamed', 'member_removed', 'member_joined', 'member_left', 'share_link_rotated', "
    "'trip_locked', 'trip_unlocked', 'trip_closed', 'trip_reopened')"
)


def _uuid_pk() -> sa.Column[object]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _created_at() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated_at() -> sa.Column[object]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _trip_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["trip_id"], ["trips.id"], name=op.f(f"fk_{table}_trip_id_trips"), ondelete="CASCADE"
    )


def _member_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["trip_id", column],
        ["members.trip_id", "members.id"],
        name=op.f(f"fk_{table}_trip_id_{column}_members"),
        ondelete="NO ACTION",
        initially="DEFERRED",
        deferrable=True,
    )


def _create_trip_core_tables() -> None:
    op.create_table(
        "trips",
        _uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), server_default="VND", nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("fund_holder_id", sa.Uuid(), nullable=True),
        sa.Column("share_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("share_token_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_trips_currency_code")),
        sa.CheckConstraint(
            r"name ~ '\S' AND char_length(name) <= 80", name=op.f("ck_trips_name_length")
        ),
        sa.CheckConstraint("ends_on >= starts_on", name=op.f("ck_trips_dates_ordered")),
        sa.CheckConstraint(
            "octet_length(share_token_hash) = 32", name=op.f("ck_trips_share_token_hash_length")
        ),
        sa.CheckConstraint(
            "share_token_version >= 1", name=op.f("ck_trips_share_token_version_min")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trips")),
        sa.UniqueConstraint("share_token_hash", name=op.f("uq_trips_share_token_hash")),
    )
    op.create_table(
        "members",
        _uuid_pk(),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        _created_at(),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            r"display_name ~ '\S' AND char_length(display_name) <= 40",
            name=op.f("ck_members_display_name_length"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_members_position_non_negative")),
        _trip_fk("members"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sa.UniqueConstraint("trip_id", "id", name=op.f("uq_members_trip_id_id")),
        sa.UniqueConstraint("trip_id", "position", name=op.f("uq_members_trip_id_position")),
    )
    op.create_index(
        "uq_members_trip_id_lower_display_name",
        "members",
        ["trip_id", sa.literal_column("lower(display_name)")],
        unique=True,
        postgresql_where=sa.text("removed_at IS NULL"),
    )
    op.create_foreign_key(
        op.f("fk_trips_id_fund_holder_id_members"),
        "trips",
        "members",
        ["id", "fund_holder_id"],
        ["trip_id", "id"],
        ondelete="NO ACTION",
        deferrable=True,
        initially="DEFERRED",
    )


def _create_ledger_tables() -> None:
    op.create_table(
        "expenses",
        _uuid_pk(),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_by_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("place", sa.Text(), nullable=True),
        sa.Column("split_mode", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"category IN {_CATEGORIES}", name=op.f("ck_expenses_category_known")),
        sa.CheckConstraint(
            f"split_mode IN {_SPLIT_MODES}", name=op.f("ck_expenses_split_mode_known")
        ),
        sa.CheckConstraint(
            r"title ~ '\S' AND char_length(title) <= 120", name=op.f("ck_expenses_title_length")
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_expenses_amount_non_negative")),
        sa.CheckConstraint(
            r"note ~ '\S' AND char_length(note) <= 500", name=op.f("ck_expenses_note_length")
        ),
        sa.CheckConstraint(
            r"place ~ '\S' AND char_length(place) <= 200", name=op.f("ck_expenses_place_length")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_expenses_version_min")),
        _member_fk("expenses", "created_by_id"),
        _member_fk("expenses", "paid_by_id"),
        _member_fk("expenses", "updated_by_id"),
        _trip_fk("expenses"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
        sa.UniqueConstraint("trip_id", "id", name=op.f("uq_expenses_trip_id_id")),
    )
    op.create_index(
        "ix_expenses_trip_id_spent_on",
        "expenses",
        ["trip_id", "spent_on"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "expense_shares",
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("weight", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_expense_shares_amount_non_negative")),
        sa.CheckConstraint("weight >= 0", name=op.f("ck_expense_shares_weight_non_negative")),
        sa.ForeignKeyConstraint(
            ["trip_id", "expense_id"],
            ["expenses.trip_id", "expenses.id"],
            name=op.f("fk_expense_shares_trip_id_expense_id_expenses"),
            ondelete="CASCADE",
        ),
        _member_fk("expense_shares", "member_id"),
        sa.PrimaryKeyConstraint("expense_id", "member_id", name=op.f("pk_expense_shares")),
    )
    op.create_index(
        "ix_expense_shares_trip_id_member_id",
        "expense_shares",
        ["trip_id", "member_id"],
        unique=False,
    )
    op.create_table(
        "fund_contributions",
        _uuid_pk(),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("contributed_on", sa.Date(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        _created_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name=op.f("ck_fund_contributions_amount_positive")),
        _member_fk("fund_contributions", "created_by_id"),
        _member_fk("fund_contributions", "member_id"),
        _trip_fk("fund_contributions"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fund_contributions")),
    )
    op.create_index(
        "ix_fund_contributions_trip_id", "fund_contributions", ["trip_id"], unique=False
    )
    op.create_table(
        "payments",
        _uuid_pk(),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("payer_id", sa.Uuid(), nullable=False),
        sa.Column("payee_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        _created_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount_positive")),
        sa.CheckConstraint("payer_id <> payee_id", name=op.f("ck_payments_payer_is_not_payee")),
        sa.CheckConstraint(
            r"note ~ '\S' AND char_length(note) <= 200", name=op.f("ck_payments_note_length")
        ),
        _member_fk("payments", "created_by_id"),
        _member_fk("payments", "payee_id"),
        _member_fk("payments", "payer_id"),
        _trip_fk("payments"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
    )
    op.create_index(
        "ix_payments_trip_id_paid_on_created_at_id",
        "payments",
        ["trip_id", "paid_on", "created_at", "id"],
        unique=False,
    )


def _create_bank_and_event_tables() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("bank_bin", sa.Text(), nullable=False),
        sa.Column("account_number_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("account_last4", sa.Text(), nullable=False),
        sa.Column("account_name", sa.Text(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "bank_bin ~ '^[0-9]{6}$'", name=op.f("ck_bank_accounts_bank_bin_format")
        ),
        sa.CheckConstraint(
            "account_last4 ~ '^[0-9]{4}$'", name=op.f("ck_bank_accounts_account_last4_format")
        ),
        sa.CheckConstraint(
            "account_name ~ '^[A-Z]+( [A-Z]+)*$' AND char_length(account_name) <= 50",
            name=op.f("ck_bank_accounts_account_name_format"),
        ),
        _member_fk("bank_accounts", "member_id"),
        _trip_fk("bank_accounts"),
        sa.PrimaryKeyConstraint("trip_id", "member_id", name=op.f("pk_bank_accounts")),
    )
    op.create_table(
        "trip_events",
        _uuid_pk(),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("actor_member_id", sa.Uuid(), nullable=True),
        sa.Column("subject_member_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        _created_at(),
        sa.CheckConstraint(f"kind IN {_EVENT_KINDS}", name=op.f("ck_trip_events_kind_known")),
        _member_fk("trip_events", "actor_member_id"),
        _member_fk("trip_events", "subject_member_id"),
        _trip_fk("trip_events"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_events")),
    )
    op.create_index(
        "ix_trip_events_trip_id_created_at_id",
        "trip_events",
        ["trip_id", "created_at", "id"],
        unique=False,
    )


def _create_session_tables() -> None:
    op.create_table(
        "devices",
        _uuid_pk(),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        _created_at(),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name=op.f("ck_devices_token_hash_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_devices_token_hash")),
    )
    op.create_index("ix_devices_expires_at", "devices", ["expires_at"], unique=False)
    op.create_index(
        "ix_devices_revoked_at",
        "devices",
        ["revoked_at"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NOT NULL"),
    )
    op.create_table(
        "memberships",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        _created_at(),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_memberships_device_id_devices"),
            ondelete="CASCADE",
        ),
        _member_fk("memberships", "member_id"),
        _trip_fk("memberships"),
        sa.PrimaryKeyConstraint("device_id", "trip_id", name=op.f("pk_memberships")),
    )
    op.create_index(
        "ix_memberships_trip_id_member_id", "memberships", ["trip_id", "member_id"], unique=False
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.LargeBinary(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "octet_length(request_hash) = 32",
            name=op.f("ck_idempotency_keys_request_hash_length"),
        ),
        sa.CheckConstraint(
            "(status_code IS NULL) = (response_body IS NULL)",
            name=op.f("ck_idempotency_keys_response_complete"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name=op.f("fk_idempotency_keys_device_id_devices"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("device_id", "key", name=op.f("pk_idempotency_keys")),
    )
    op.create_index(
        "ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"], unique=False
    )


def upgrade() -> None:
    _create_trip_core_tables()
    _create_ledger_tables()
    _create_bank_and_event_tables()
    _create_session_tables()


def downgrade() -> None:
    op.drop_constraint(op.f("fk_trips_id_fund_holder_id_members"), "trips", type_="foreignkey")
    for table in (
        "idempotency_keys",
        "memberships",
        "devices",
        "trip_events",
        "bank_accounts",
        "payments",
        "fund_contributions",
        "expense_shares",
        "expenses",
        "members",
        "trips",
    ):
        op.drop_table(table)
