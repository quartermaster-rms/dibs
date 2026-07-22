"""Helpers to insert domain rows in tests."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from dibs.enums import (
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
from dibs.models import (
    Equipment,
    EquipmentClass,
    InterlockNode,
    IssueReport,
    Location,
    QuotaPolicy,
    Reservation,
    RoleGrant,
    Session,
)


async def make_location(session: AsyncSession, building: str = "Building A", room: str = "101"):
    loc = Location(building=building, room=room)
    session.add(loc)
    await session.flush()
    return loc


async def make_class(
    session: AsyncSession,
    name: str | None = None,
    open_use: bool = False,
    requires_enable: bool = True,
    department_groups: list[str] | None = None,
):
    ec = EquipmentClass(
        name=name or f"class-{uuid.uuid4().hex[:8]}",
        description="",
        open_use=open_use,
        requires_enable=requires_enable,
        department_groups=department_groups or [],
    )
    session.add(ec)
    await session.flush()
    return ec


async def make_equipment(
    session: AsyncSession,
    klass: EquipmentClass | None = None,
    location: Location | None = None,
    name: str = "Widget",
    open_use: bool = False,
    requires_enable: bool = True,
    qr_token: str | None = None,
):
    if klass is None:
        klass = await make_class(session)
    if location is None:
        location = await make_location(session, room=uuid.uuid4().hex[:6])
    eq = Equipment(
        name=name,
        class_id=klass.id,
        location_id=location.id,
        open_use=open_use,
        requires_enable=requires_enable,
        qr_token=qr_token or uuid.uuid4().hex,
    )
    session.add(eq)
    await session.flush()
    return eq


async def make_grant(
    session: AsyncSession,
    subject: str,
    scope_kind: ScopeKind,
    scope_id: uuid.UUID,
    tier: Tier,
    granted_by: str = "admin",
    can_promote: bool = False,
    can_grant_superuser: bool = False,
    can_demote: bool = False,
):
    g = RoleGrant(
        subject=subject,
        scope_kind=scope_kind,
        scope_id=scope_id,
        tier=tier,
        granted_by=granted_by,
        can_promote=can_promote,
        can_grant_superuser=can_grant_superuser,
        can_demote=can_demote,
    )
    session.add(g)
    await session.flush()
    return g


async def make_reservation(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    user_id: str,
    starts_at: datetime,
    ends_at: datetime,
    status: ReservationStatus = ReservationStatus.BOOKED,
    created_by: str | None = None,
):
    r = Reservation(
        equipment_id=equipment_id,
        user_id=user_id,
        created_by=created_by or user_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
    )
    session.add(r)
    await session.flush()
    return r


async def make_quota_policy(
    session: AsyncSession,
    quota_type: QuotaType,
    principal: str,
    target_kind: ScopeKind,
    target_id: uuid.UUID,
    window: QuotaWindow,
    limit_hours: float,
    hard_cap: bool = False,
):
    p = QuotaPolicy(
        quota_type=quota_type,
        principal=principal,
        target_kind=target_kind,
        target_id=target_id,
        window=window,
        limit_hours=Decimal(str(limit_hours)),
        hard_cap=hard_cap,
    )
    session.add(p)
    await session.flush()
    return p


async def make_node(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    enabled: bool = True,
    fail_state: FailState = FailState.FAIL_ENABLED,
    key: str = "node-key",
    poll_interval_s: int = 5,
    heartbeat_interval_s: int = 30,
    name: str = "node",
):
    from dibs.device.keys import hash_key

    n = InterlockNode(
        equipment_id=equipment_id,
        key_hash=hash_key(key),
        fail_state=fail_state,
        poll_interval_s=poll_interval_s,
        heartbeat_interval_s=heartbeat_interval_s,
        enabled=enabled,
        name=name,
    )
    session.add(n)
    await session.flush()
    return n


async def make_issue(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    reporter_id: str = "reporter",
    severity: Severity = Severity.FATAL,
    status: IssueStatus = IssueStatus.OPEN,
    title: str = "Broken",
    description: str = "",
):
    i = IssueReport(
        equipment_id=equipment_id,
        reporter_id=reporter_id,
        title=title,
        severity=severity,
        description=description,
        status=status,
    )
    session.add(i)
    await session.flush()
    return i


async def make_session(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    user_id: str,
    started_at: datetime,
    ended_at: datetime | None = None,
    end_cause: EndCause | None = None,
):
    s = Session(
        equipment_id=equipment_id,
        user_id=user_id,
        started_at=started_at,
        ended_at=ended_at,
        end_cause=end_cause,
    )
    session.add(s)
    await session.flush()
    return s
