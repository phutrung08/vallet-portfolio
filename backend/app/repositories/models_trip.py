import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.constants import EXPENSE_CATEGORIES, SPLIT_MODES
from app.repositories.models_base import (
    EVENT_KINDS,
    SHA256_BYTES,
    Base,
    _member_fk,
    _one_of,
    _text_length,
    _trip_fk,
    _uuid_pk,
)


class Trip(Base):
    """A shared trip ledger with currency, optional shared fund holder, and lifecycle timestamps."""

    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint(_text_length("name", 80), name="name_length"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_code"),
        CheckConstraint("ends_on >= starts_on", name="dates_ordered"),
        CheckConstraint(
            f"octet_length(share_token_hash) = {SHA256_BYTES}", name="share_token_hash_length"
        ),
        CheckConstraint("share_token_version >= 1", name="share_token_version_min"),
        _member_fk("fund_holder_id", trip_column="id", use_alter=True),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str]
    currency: Mapped[str] = mapped_column(default="VND", server_default="VND")
    starts_on: Mapped[date | None]
    ends_on: Mapped[date | None]
    fund_holder_id: Mapped[uuid.UUID | None]
    share_token_hash: Mapped[bytes] = mapped_column(unique=True)
    share_token_version: Mapped[int] = mapped_column(default=1, server_default="1")
    locked_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Member(Base):
    """A named participant within a single trip (soft-removed rather than hard-deleted)."""

    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint(_text_length("display_name", 40), name="display_name_length"),
        CheckConstraint("position >= 0", name="position_non_negative"),
        UniqueConstraint("trip_id", "position"),
        UniqueConstraint("trip_id", "id"),
        Index(
            "uq_members_trip_id_lower_display_name",
            "trip_id",
            func.lower(text("display_name")),
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    trip_id: Mapped[uuid.UUID] = _trip_fk()
    display_name: Mapped[str]
    position: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    removed_at: Mapped[datetime | None]


class Expense(Base):
    """A single trip expense paid by a member or the shared fund (``paid_by_id is None``)."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint(_text_length("title", 120), name="title_length"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint(_one_of("category", EXPENSE_CATEGORIES), name="category_known"),
        CheckConstraint(_one_of("split_mode", SPLIT_MODES), name="split_mode_known"),
        CheckConstraint(_text_length("note", 500), name="note_length"),
        CheckConstraint(_text_length("place", 200), name="place_length"),
        CheckConstraint("version >= 1", name="version_min"),
        UniqueConstraint("trip_id", "id"),
        _member_fk("paid_by_id"),
        _member_fk("created_by_id"),
        _member_fk("updated_by_id"),
        Index(
            "ix_expenses_trip_id_spent_on",
            "trip_id",
            "spent_on",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    trip_id: Mapped[uuid.UUID] = _trip_fk()
    title: Mapped[str]
    amount: Mapped[int] = mapped_column(BigInteger)
    paid_by_id: Mapped[uuid.UUID | None]
    category: Mapped[str]
    spent_on: Mapped[date]
    note: Mapped[str | None]
    place: Mapped[str | None]
    split_mode: Mapped[str]
    created_by_id: Mapped[uuid.UUID]
    updated_by_id: Mapped[uuid.UUID | None]
    # Bumped by every edit; an edit naming an older version is refused (optimistic concurrency).
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None]


class ExpenseShare(Base):
    """One member's allocated integer share and weight within an expense."""

    __tablename__ = "expense_shares"
    __table_args__ = (
        CheckConstraint("weight >= 0", name="weight_non_negative"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        ForeignKeyConstraint(
            ["trip_id", "expense_id"], ["expenses.trip_id", "expenses.id"], ondelete="CASCADE"
        ),
        _member_fk("member_id"),
        Index("ix_expense_shares_trip_id_member_id", "trip_id", "member_id"),
    )

    expense_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    trip_id: Mapped[uuid.UUID]
    weight: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(BigInteger)


class FundContribution(Base):
    """A deposit into the trip's shared cash fund."""

    __tablename__ = "fund_contributions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        _member_fk("member_id"),
        _member_fk("created_by_id"),
        Index("ix_fund_contributions_trip_id", "trip_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    trip_id: Mapped[uuid.UUID] = _trip_fk()
    member_id: Mapped[uuid.UUID]
    amount: Mapped[int] = mapped_column(BigInteger)
    contributed_on: Mapped[date]
    created_by_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class Payment(Base):
    """A settlement payment between two members; it moves both nets, never the expenses."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("payer_id <> payee_id", name="payer_is_not_payee"),
        CheckConstraint(_text_length("note", 200), name="note_length"),
        _member_fk("payer_id"),
        _member_fk("payee_id"),
        _member_fk("created_by_id"),
        # Trip-led and not partial, so it also backs the trip cascade and the member FK checks,
        # which see deleted rows too. Scanned backward it gives the list its newest-first order.
        Index(
            "ix_payments_trip_id_paid_on_created_at_id", "trip_id", "paid_on", "created_at", "id"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    trip_id: Mapped[uuid.UUID] = _trip_fk()
    payer_id: Mapped[uuid.UUID]
    payee_id: Mapped[uuid.UUID]
    amount: Mapped[int] = mapped_column(BigInteger)
    paid_on: Mapped[date]
    note: Mapped[str | None]
    created_by_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class BankAccount(Base):
    """A member's own bank account for VietQR. The number is AES-GCM ciphertext (core.crypto)."""

    __tablename__ = "bank_accounts"
    __table_args__ = (
        CheckConstraint("bank_bin ~ '^[0-9]{6}$'", name="bank_bin_format"),
        CheckConstraint("account_last4 ~ '^[0-9]{4}$'", name="account_last4_format"),
        CheckConstraint(
            "account_name ~ '^[A-Z]+( [A-Z]+)*$' AND char_length(account_name) <= 50",
            name="account_name_format",
        ),
        _member_fk("member_id"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    bank_bin: Mapped[str]
    account_number_encrypted: Mapped[bytes]
    account_last4: Mapped[str]
    account_name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TripEvent(Base):
    """One entry of the trip's activity log: who did what, never the sensitive values involved."""

    __tablename__ = "trip_events"
    __table_args__ = (
        CheckConstraint(_one_of("kind", EVENT_KINDS), name="kind_known"),
        _member_fk("actor_member_id"),
        _member_fk("subject_member_id"),
        Index("ix_trip_events_trip_id_created_at_id", "trip_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    trip_id: Mapped[uuid.UUID] = _trip_fk()
    actor_member_id: Mapped[uuid.UUID | None]
    subject_member_id: Mapped[uuid.UUID | None]
    kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
