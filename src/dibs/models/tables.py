"""ORM table definitions. The initial migration is the source of truth for
exotic DB constraints (GiST exclusion, partial unique index, triggers, CHECKs);
these classes mirror the columns for ORM use."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..enums import (
    EndCause,
    FailState,
    IssueStatus,
    QuotaType,
    QuotaWindow,
    ReservationStatus,
    ScopeKind,
    Severity,
    Tier,
)
from .base import Base, TimestampMixin, uuid_pk

SUBJECT = String(255)


def _enum(py, name):  # noqa: ANN001
    return Enum(py, native_enum=False, length=32, name=name, validate_strings=True)


class Location(TimestampMixin, Base):
    __tablename__ = "location"
    __table_args__ = (UniqueConstraint("building", "room", name="uq_location_building_room"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    building: Mapped[str] = mapped_column(String(255), nullable=False)
    room: Mapped[str] = mapped_column(String(255), nullable=False)


class EquipmentClass(TimestampMixin, Base):
    __tablename__ = "equipment_class"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    department_groups: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    open_use: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    requires_enable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Equipment(TimestampMixin, Base):
    __tablename__ = "equipment"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment_class.id"), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("location.id"), nullable=False)
    photo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    requires_enable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    open_use: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    qr_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    equipment_class: Mapped[EquipmentClass] = relationship(lazy="raise")
    location: Mapped[Location] = relationship(lazy="raise")
    nodes: Mapped[list[InterlockNode]] = relationship(
        back_populates="equipment", lazy="raise", cascade="all, delete-orphan"
    )


class Reservation(TimestampMixin, Base):
    __tablename__ = "reservation"
    __table_args__ = (CheckConstraint("ends_at > starts_at", name="ends_after_starts"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    created_by: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        _enum(ReservationStatus, "reservation_status"),
        nullable=False,
        server_default=ReservationStatus.BOOKED.value,
    )


class Session(TimestampMixin, Base):
    __tablename__ = "session"
    __table_args__ = (
        Index(
            "uq_session_one_live",
            "equipment_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_cause: Mapped[EndCause | None] = mapped_column(_enum(EndCause, "end_cause"), nullable=True)


class QuotaPolicy(TimestampMixin, Base):
    __tablename__ = "quota_policy"
    id: Mapped[uuid.UUID] = uuid_pk()
    quota_type: Mapped[QuotaType] = mapped_column(_enum(QuotaType, "quota_type"), nullable=False)
    principal: Mapped[str] = mapped_column(String(320), nullable=False)
    target_kind: Mapped[ScopeKind] = mapped_column(
        _enum(ScopeKind, "quota_target_kind"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    window: Mapped[QuotaWindow] = mapped_column(_enum(QuotaWindow, "quota_window"), nullable=False)
    limit_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    hard_cap: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class IssueReport(TimestampMixin, Base):
    __tablename__ = "issue_report"
    id: Mapped[uuid.UUID] = uuid_pk()
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    reporter_id: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[Severity] = mapped_column(_enum(Severity, "severity"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[IssueStatus] = mapped_column(
        _enum(IssueStatus, "issue_status"), nullable=False, server_default=IssueStatus.OPEN.value
    )
    closed_by: Mapped[str | None] = mapped_column(SUBJECT, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updates: Mapped[list[IssueUpdate]] = relationship(
        back_populates="issue", lazy="raise", cascade="all, delete-orphan"
    )
    photos: Mapped[list[IssuePhoto]] = relationship(
        back_populates="issue", lazy="raise", cascade="all, delete-orphan"
    )


class IssueUpdate(Base):
    __tablename__ = "issue_update"
    id: Mapped[uuid.UUID] = uuid_pk()
    issue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issue_report.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    issue: Mapped[IssueReport] = relationship(back_populates="updates", lazy="raise")


class IssuePhoto(Base):
    __tablename__ = "issue_photo"
    id: Mapped[uuid.UUID] = uuid_pk()
    issue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issue_report.id"), nullable=False)
    update_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("issue_update.id"), nullable=True
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    issue: Mapped[IssueReport] = relationship(back_populates="photos", lazy="raise")


class InterlockNode(TimestampMixin, Base):
    __tablename__ = "interlock_node"
    id: Mapped[uuid.UUID] = uuid_pk()
    equipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    prev_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fail_state: Mapped[FailState] = mapped_column(_enum(FailState, "fail_state"), nullable=False)
    poll_interval_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    heartbeat_interval_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_firmware: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offline: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    equipment: Mapped[Equipment] = relationship(back_populates="nodes", lazy="raise")


class Notification(Base):
    __tablename__ = "notification"
    id: Mapped[uuid.UUID] = uuid_pk()
    recipient: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Principal(Base):
    __tablename__ = "principal"
    subject: Mapped[str] = mapped_column(SUBJECT, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    groups: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RoleGrant(TimestampMixin, Base):
    __tablename__ = "role_grant"
    __table_args__ = (
        UniqueConstraint("subject", "scope_kind", "scope_id", name="uq_role_grant_scope"),
        CheckConstraint(
            "tier = 'superuser' OR "
            "(NOT can_promote AND NOT can_grant_superuser AND NOT can_demote)",
            name="user_tier_no_flags",
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    subject: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    scope_kind: Mapped[ScopeKind] = mapped_column(
        _enum(ScopeKind, "grant_scope_kind"), nullable=False
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tier: Mapped[Tier] = mapped_column(_enum(Tier, "grant_tier"), nullable=False)
    granted_by: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    can_promote: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    can_grant_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    can_demote: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class Setting(TimestampMixin, Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[uuid.UUID] = uuid_pk()
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_key"
    __table_args__ = (UniqueConstraint("caller", "key", name="uq_idempotency_caller_key"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    caller: Mapped[str] = mapped_column(SUBJECT, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
