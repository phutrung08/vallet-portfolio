import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.repositories.models_base import SHA256_BYTES, Base, _member_fk, _uuid_pk


class Device(Base):
    """A browser holding an opaque session token in an HttpOnly cookie; no account behind it."""

    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(f"octet_length(token_hash) = {SHA256_BYTES}", name="token_hash_length"),
        # The cleanup job finds devices past their expiry or revocation by range scan.
        Index("ix_devices_expires_at", "expires_at"),
        Index(
            "ix_devices_revoked_at", "revoked_at", postgresql_where=text("revoked_at IS NOT NULL")
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    token_hash: Mapped[bytes] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]


class Membership(Base):
    """Which member of a trip a device acts as; one identity per device per trip."""

    __tablename__ = "memberships"
    __table_args__ = (
        _member_fk("member_id"),
        # The primary key (device_id, trip_id) serves "trips on this device" and the device
        # cascade; this index finds a member's devices and backs the trip/member cascades.
        Index("ix_memberships_trip_id_member_id", "trip_id", "member_id"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[datetime | None]


class IdempotencyKey(Base):
    """A create a device already sent, so a retry replays the stored response instead of writing."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        CheckConstraint(f"octet_length(request_hash) = {SHA256_BYTES}", name="request_hash_length"),
        CheckConstraint(
            "(status_code IS NULL) = (response_body IS NULL)", name="response_complete"
        ),
        # The cleanup job deletes keys by age.
        Index("ix_idempotency_keys_created_at", "created_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    route: Mapped[str]
    request_hash: Mapped[bytes]
    status_code: Mapped[int | None]
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
