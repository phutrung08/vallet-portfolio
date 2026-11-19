import uuid
from datetime import datetime
from typing import Literal, get_args

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, MetaData, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}

SHA256_BYTES = 32

# What the trip log can say. Never account numbers or names: the kind and the members suffice.
EventKind = Literal[
    "bank_account_set",
    "bank_account_removed",
    "fund_holder_changed",
    "member_added",
    "member_renamed",
    "member_removed",
    "member_joined",
    "member_left",
    "share_link_rotated",
    "trip_locked",
    "trip_unlocked",
    "trip_closed",
    "trip_reopened",
]
EVENT_KINDS: tuple[str, ...] = get_args(EventKind)


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _text_length(column: str, max_chars: int) -> str:
    return rf"{column} ~ '\S' AND char_length({column}) <= {max_chars}"


# Every member reference is a composite FK (trip_id, member) -> members(trip_id, id), so a row
# can never point at a member of another trip. Deferred to commit: a trip delete cascades to
# members and to the rows that reference them in an unspecified order, and an immediate check
# would fire in between. Members are soft-removed, so a hard delete still fails at commit
# while anything references them.
def _member_fk(
    member_column: str, trip_column: str = "trip_id", use_alter: bool = False
) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        [trip_column, member_column],
        ["members.trip_id", "members.id"],
        ondelete="NO ACTION",
        deferrable=True,
        initially="DEFERRED",
        use_alter=use_alter,
    )


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def _trip_fk() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base with deterministic constraint naming."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True), str: Text}
