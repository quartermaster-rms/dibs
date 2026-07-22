"""Helpers to insert domain rows in tests."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from dibs.enums import ScopeKind, Tier
from dibs.models import Equipment, EquipmentClass, Location, RoleGrant


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
