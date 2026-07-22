"""Resolve a caller's effective access to a piece of equipment: department-gate
reachability, open access, enable-gating, and effective fine tier."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..enums import ScopeKind, Tier
from ..errors import NotFound
from ..models import Equipment, EquipmentClass, RoleGrant
from ..services.settings import get_setting
from .tiers import can_operate, department_gate_ok, effective_tier, is_enable_gated, is_open_access


@dataclass(frozen=True)
class Access:
    equipment_id: uuid.UUID
    class_id: uuid.UUID
    is_admin: bool
    reachable: bool
    open_access: bool
    enable_gated: bool
    tier: Tier

    @property
    def can_operate(self) -> bool:
        return self.reachable and can_operate(self.is_admin, self.tier)


def compute_access(
    *,
    identity: Identity,
    equipment: Equipment,
    klass: EquipmentClass,
    dibs_gate: set[str],
    item_tier: Tier | None,
    class_tier: Tier | None,
) -> Access:
    is_admin = identity.is_admin
    groups = set(identity.groups)
    reachable = department_gate_ok(is_admin, groups, dibs_gate) and department_gate_ok(
        is_admin, groups, set(klass.department_groups)
    )
    open_access = is_open_access(equipment.open_use, klass.open_use)
    enable_gated = is_enable_gated(equipment.requires_enable, klass.requires_enable)
    tier = effective_tier(item_tier, class_tier, open_access) if reachable else Tier.NONE
    return Access(
        equipment_id=equipment.id,
        class_id=klass.id,
        is_admin=is_admin,
        reachable=reachable,
        open_access=open_access,
        enable_gated=enable_gated,
        tier=tier,
    )


async def _grant_tiers(
    session: AsyncSession, subject: str, equipment_id: uuid.UUID, class_id: uuid.UUID
) -> tuple[Tier | None, Tier | None]:
    rows = (
        await session.execute(
            select(RoleGrant.scope_kind, RoleGrant.scope_id, RoleGrant.tier).where(
                RoleGrant.subject == subject,
                or_(
                    (RoleGrant.scope_kind == ScopeKind.ITEM) & (RoleGrant.scope_id == equipment_id),
                    (RoleGrant.scope_kind == ScopeKind.CLASS) & (RoleGrant.scope_id == class_id),
                ),
            )
        )
    ).all()
    item_tier: Tier | None = None
    class_tier: Tier | None = None
    for scope_kind, _scope_id, tier in rows:
        if scope_kind == ScopeKind.ITEM:
            item_tier = tier
        else:
            class_tier = tier
    return item_tier, class_tier


async def reachable_equipment_ids(
    session: AsyncSession, identity: Identity
) -> set[uuid.UUID] | None:
    """The equipment the caller may reach through the department gate. None means
    'all' (admins bypass the gate)."""
    if identity.is_admin:
        return None
    groups = set(identity.groups)
    dibs_gate = set(await get_setting(session, "dibs_department_groups"))
    if not department_gate_ok(False, groups, dibs_gate):
        return set()
    rows = await session.execute(
        select(Equipment.id, EquipmentClass.department_groups).join(
            EquipmentClass, Equipment.class_id == EquipmentClass.id
        )
    )
    return {eq_id for eq_id, dept in rows if department_gate_ok(False, groups, set(dept))}


async def load_access(session: AsyncSession, identity: Identity, equipment_id: uuid.UUID) -> Access:
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise NotFound("equipment not found")
    klass = await session.get(EquipmentClass, equipment.class_id)
    dibs_gate = set(await get_setting(session, "dibs_department_groups"))
    item_tier, class_tier = await _grant_tiers(
        session, identity.subject, equipment_id, equipment.class_id
    )
    return compute_access(
        identity=identity,
        equipment=equipment,
        klass=klass,
        dibs_gate=dibs_gate,
        item_tier=item_tier,
        class_tier=class_tier,
    )
