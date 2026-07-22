"""Fine-tier grants: rosters and the PUT /grants transition, evaluated against
the caller's configured delegation abilities."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..enums import ScopeKind, Tier
from ..errors import NotFound
from ..models import Equipment, EquipmentClass, Principal, RoleGrant
from ..permissions.access import load_access
from ..permissions.delegation import (
    ActorGrant,
    GrantFlags,
    actor_flags_for_target,
    authorize_transition,
)
from .settings import get_setting


def _flags_of(g: RoleGrant) -> GrantFlags:
    return GrantFlags(g.can_promote, g.can_grant_superuser, g.can_demote)


def _grant_dict(g: RoleGrant, name: str | None = None, email: str | None = None) -> dict:
    return {
        "subject": g.subject,
        "display_name": name,
        "email": email,
        "scope_kind": g.scope_kind.value,
        "scope_id": str(g.scope_id),
        "tier": g.tier.value,
        "can_promote": g.can_promote,
        "can_grant_superuser": g.can_grant_superuser,
        "can_demote": g.can_demote,
        "granted_by": g.granted_by,
    }


async def _roster(session: AsyncSession, condition, q: str | None) -> list[dict]:
    rows = (
        await session.execute(
            select(RoleGrant, Principal)
            .outerjoin(Principal, Principal.subject == RoleGrant.subject)
            .where(condition, RoleGrant.tier.in_((Tier.USER, Tier.SUPERUSER)))
        )
    ).all()
    result = []
    for grant, principal in rows:
        if principal is not None and principal.is_admin:
            continue  # admins hold no per-scope grant and aren't listed
        name = principal.display_name if principal else None
        email = principal.email if principal else None
        if q:
            hay = f"{grant.subject} {name or ''} {email or ''}".lower()
            if q.lower() not in hay:
                continue
        result.append(_grant_dict(grant, name, email))
    return result


async def list_item_grants(
    session: AsyncSession, identity: Identity, equipment_id: uuid.UUID, q: str | None
) -> list[dict]:
    access = await load_access(session, identity, equipment_id)
    condition = or_(
        (RoleGrant.scope_kind == ScopeKind.ITEM) & (RoleGrant.scope_id == equipment_id),
        (RoleGrant.scope_kind == ScopeKind.CLASS) & (RoleGrant.scope_id == access.class_id),
    )
    return await _roster(session, condition, q)


async def list_class_grants(
    session: AsyncSession, identity: Identity, class_id: uuid.UUID, q: str | None
) -> list[dict]:
    if await session.get(EquipmentClass, class_id) is None:
        raise NotFound("class not found")
    condition = (RoleGrant.scope_kind == ScopeKind.CLASS) & (RoleGrant.scope_id == class_id)
    return await _roster(session, condition, q)


async def _actor_covering(
    session: AsyncSession,
    actor_subject: str,
    scope_kind: ScopeKind,
    scope_id: uuid.UUID,
    item_class_id: str | None,
) -> list[ActorGrant]:
    conds = []
    if scope_kind == ScopeKind.ITEM:
        conds.append((RoleGrant.scope_kind == ScopeKind.ITEM) & (RoleGrant.scope_id == scope_id))
        if item_class_id is not None:
            conds.append(
                (RoleGrant.scope_kind == ScopeKind.CLASS)
                & (RoleGrant.scope_id == uuid.UUID(item_class_id))
            )
    else:
        conds.append((RoleGrant.scope_kind == ScopeKind.CLASS) & (RoleGrant.scope_id == scope_id))
    rows = (
        await session.execute(
            select(RoleGrant).where(
                RoleGrant.subject == actor_subject,
                RoleGrant.tier == Tier.SUPERUSER,
                or_(*conds),
            )
        )
    ).scalars()
    return [ActorGrant(g.scope_kind, str(g.scope_id), g.tier, _flags_of(g)) for g in rows]


async def _default_flags(session: AsyncSession) -> GrantFlags:
    return GrantFlags(
        await get_setting(session, "delegation_default_can_promote"),
        await get_setting(session, "delegation_default_can_grant_superuser"),
        await get_setting(session, "delegation_default_can_demote"),
    )


async def put_grant(
    session: AsyncSession,
    actor: Identity,
    subject: str,
    scope_kind: ScopeKind,
    scope_id: uuid.UUID,
    new_tier: Tier,
    flags: GrantFlags | None,
) -> tuple[dict, dict]:
    if scope_kind == ScopeKind.ITEM:
        equipment = await session.get(Equipment, scope_id)
        if equipment is None:
            raise NotFound("equipment not found")
        item_class_id: str | None = str(equipment.class_id)
    else:
        if await session.get(EquipmentClass, scope_id) is None:
            raise NotFound("class not found")
        item_class_id = None

    current = (
        await session.execute(
            select(RoleGrant).where(
                RoleGrant.subject == subject,
                RoleGrant.scope_kind == scope_kind,
                RoleGrant.scope_id == scope_id,
            )
        )
    ).scalar_one_or_none()
    current_tier = current.tier if current else Tier.NONE

    principal = await session.get(Principal, subject)
    target_is_admin = bool(principal and principal.is_admin)

    actor_grants = await _actor_covering(
        session, actor.subject, scope_kind, scope_id, item_class_id
    )
    actor_flags = actor_flags_for_target(actor_grants, scope_kind, str(scope_id), item_class_id)

    requested = (
        (flags if flags is not None else await _default_flags(session))
        if new_tier == Tier.SUPERUSER
        else GrantFlags()
    )

    authorize_transition(
        actor_is_admin=actor.is_admin,
        actor_flags=actor_flags,
        actor_is_target=actor.subject == subject,
        target_is_admin=target_is_admin,
        current_tier=current_tier,
        new_tier=new_tier,
        requested_flags=requested,
        allow_peer_demote=await get_setting(session, "delegation_allow_peer_demote"),
        allow_self_demote=await get_setting(session, "delegation_allow_self_demote"),
    )

    before = _grant_dict(current) if current else {"subject": subject, "tier": "none"}
    if new_tier == Tier.NONE:
        if current is not None:
            await session.delete(current)
            await session.flush()
        after = {
            "subject": subject,
            "scope_kind": scope_kind.value,
            "scope_id": str(scope_id),
            "tier": "none",
        }
    else:
        if current is None:
            current = RoleGrant(
                subject=subject,
                scope_kind=scope_kind,
                scope_id=scope_id,
                tier=new_tier,
                granted_by=actor.subject,
            )
            session.add(current)
        current.tier = new_tier
        current.can_promote = requested.can_promote
        current.can_grant_superuser = requested.can_grant_superuser
        current.can_demote = requested.can_demote
        await session.flush()
        after = _grant_dict(current)
    return before, after
