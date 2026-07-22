"""Locations, equipment classes, and equipment: admin CRUD plus the public
equipment list / detail / history / QR lookup with computed status, the caller's
effective tier, the current holder, and the next reservation."""

from __future__ import annotations

import secrets
import uuid
from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..enums import IssueStatus, ReservationStatus, ScopeKind, Severity, Tier
from ..errors import Conflict, NotFound
from ..models import (
    Equipment,
    EquipmentClass,
    InterlockNode,
    IssueReport,
    Location,
    Principal,
    Reservation,
    RoleGrant,
    Session,
)
from ..permissions.access import compute_access
from ..permissions.tiers import is_enable_gated, is_open_access
from ..timeutil import now_utc, to_wire
from .settings import get_setting
from .status import compute_status


def location_dict(loc: Location) -> dict:
    return {"id": str(loc.id), "building": loc.building, "room": loc.room}


def class_dict(cls: EquipmentClass) -> dict:
    return {
        "id": str(cls.id),
        "name": cls.name,
        "description": cls.description,
        "department_groups": list(cls.department_groups),
        "open_use": cls.open_use,
        "requires_enable": cls.requires_enable,
    }


async def _grant_lookup(session: AsyncSession, subject: str) -> dict[tuple[str, uuid.UUID], Tier]:
    rows = (
        await session.execute(
            select(RoleGrant.scope_kind, RoleGrant.scope_id, RoleGrant.tier).where(
                RoleGrant.subject == subject
            )
        )
    ).all()
    return {(sk, sid): tier for sk, sid, tier in rows}


async def _open_issue_counts(
    session: AsyncSession, equipment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    counts: dict[uuid.UUID, dict] = defaultdict(lambda: {"fatal": 0, "warning": 0})
    if not equipment_ids:
        return counts
    rows = await session.execute(
        select(IssueReport.equipment_id, IssueReport.severity, func.count())
        .where(
            IssueReport.status == IssueStatus.OPEN,
            IssueReport.equipment_id.in_(equipment_ids),
        )
        .group_by(IssueReport.equipment_id, IssueReport.severity)
    )
    for eq_id, severity, cnt in rows:
        key = "fatal" if severity == Severity.FATAL else "warning"
        counts[eq_id][key] = cnt
    return counts


async def _live_holders(
    session: AsyncSession, equipment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    if not equipment_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(Session).where(
                    Session.ended_at.is_(None), Session.equipment_id.in_(equipment_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    subjects = {s.user_id for s in rows}
    names = await _principal_names(session, subjects)
    return {
        s.equipment_id: {
            "subject": s.user_id,
            "display_name": names.get(s.user_id, s.user_id),
            "started_at": to_wire(s.started_at),
            "session_id": str(s.id),
        }
        for s in rows
    }


async def _next_reservations(
    session: AsyncSession, equipment_ids: list[uuid.UUID], now
) -> dict[uuid.UUID, dict]:
    if not equipment_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(Reservation)
                .where(
                    Reservation.status == ReservationStatus.BOOKED,
                    Reservation.ends_at > now,
                    Reservation.equipment_id.in_(equipment_ids),
                )
                .order_by(Reservation.equipment_id, Reservation.starts_at)
            )
        )
        .scalars()
        .all()
    )
    result: dict[uuid.UUID, dict] = {}
    for r in rows:
        if r.equipment_id not in result:
            result[r.equipment_id] = {
                "id": str(r.id),
                "starts_at": to_wire(r.starts_at),
                "ends_at": to_wire(r.ends_at),
                "user_id": r.user_id,
            }
    return result


async def _principal_names(session: AsyncSession, subjects: set[str]) -> dict[str, str]:
    if not subjects:
        return {}
    rows = await session.execute(
        select(Principal.subject, Principal.display_name).where(Principal.subject.in_(subjects))
    )
    return dict(rows.all())


async def _node_counts(
    session: AsyncSession, equipment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not equipment_ids:
        return {}
    rows = await session.execute(
        select(InterlockNode.equipment_id, func.count())
        .where(InterlockNode.equipment_id.in_(equipment_ids))
        .group_by(InterlockNode.equipment_id)
    )
    return dict(rows.all())


def _row(
    equipment: Equipment,
    cls: EquipmentClass,
    loc: Location,
    access,
    counts: dict,
    holder: dict | None,
    next_res: dict | None,
    node_count: int,
) -> dict:
    return {
        "id": str(equipment.id),
        "name": equipment.name,
        "class_id": str(cls.id),
        "class_name": cls.name,
        "location": location_dict(loc),
        "photo_path": equipment.photo_path,
        "qr_token": equipment.qr_token,
        "open_use": equipment.open_use,
        "requires_enable": equipment.requires_enable,
        "open_access": access.open_access,
        "enable_gated": access.enable_gated,
        "status": compute_status(counts["fatal"], counts["warning"]),
        "effective_tier": access.tier.value,
        "is_admin": access.is_admin,
        "can_operate": access.can_operate,
        "current_holder": holder,
        "next_reservation": next_res,
        "node_count": node_count,
    }


async def list_equipment(
    session: AsyncSession,
    identity: Identity,
    *,
    q: str | None = None,
    class_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    authorized: bool = False,
    enabled_by_me: bool = False,
) -> list[dict]:
    stmt = (
        select(Equipment, EquipmentClass, Location)
        .join(EquipmentClass, Equipment.class_id == EquipmentClass.id)
        .join(Location, Equipment.location_id == Location.id)
    )
    if class_id is not None:
        stmt = stmt.where(Equipment.class_id == class_id)
    if location_id is not None:
        stmt = stmt.where(Equipment.location_id == location_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Equipment.name.ilike(like),
                EquipmentClass.name.ilike(like),
                Location.building.ilike(like),
                Location.room.ilike(like),
            )
        )
    stmt = stmt.order_by(Equipment.name)
    rows = (await session.execute(stmt)).all()

    grants = await _grant_lookup(session, identity.subject)
    dibs_gate = set(await get_setting(session, "dibs_department_groups"))
    eq_ids = [eq.id for eq, _, _ in rows]
    counts = await _open_issue_counts(session, eq_ids)
    holders = await _live_holders(session, eq_ids)
    next_res = await _next_reservations(session, eq_ids, now_utc())
    node_counts = await _node_counts(session, eq_ids)

    result = []
    for equipment, cls, loc in rows:
        access = compute_access(
            identity=identity,
            equipment=equipment,
            klass=cls,
            dibs_gate=dibs_gate,
            item_tier=grants.get((ScopeKind.ITEM, equipment.id)),
            class_tier=grants.get((ScopeKind.CLASS, cls.id)),
        )
        if not access.reachable:
            continue
        holder = holders.get(equipment.id)
        if authorized and not access.can_operate:
            continue
        if enabled_by_me and (holder is None or holder["subject"] != identity.subject):
            continue
        result.append(
            _row(
                equipment,
                cls,
                loc,
                access,
                counts[equipment.id],
                holder,
                next_res.get(equipment.id),
                node_counts.get(equipment.id, 0),
            )
        )
    return result


async def _load_triplet(session: AsyncSession, equipment_id: uuid.UUID):
    row = (
        await session.execute(
            select(Equipment, EquipmentClass, Location)
            .join(EquipmentClass, Equipment.class_id == EquipmentClass.id)
            .join(Location, Equipment.location_id == Location.id)
            .where(Equipment.id == equipment_id)
        )
    ).first()
    if row is None:
        raise NotFound("equipment not found")
    return row


async def get_equipment(session: AsyncSession, identity: Identity, equipment_id: uuid.UUID) -> dict:
    equipment, cls, loc = await _load_triplet(session, equipment_id)
    grants = await _grant_lookup(session, identity.subject)
    dibs_gate = set(await get_setting(session, "dibs_department_groups"))
    access = compute_access(
        identity=identity,
        equipment=equipment,
        klass=cls,
        dibs_gate=dibs_gate,
        item_tier=grants.get((ScopeKind.ITEM, equipment.id)),
        class_tier=grants.get((ScopeKind.CLASS, cls.id)),
    )
    if not access.reachable:
        raise NotFound("equipment not found")
    counts = (await _open_issue_counts(session, [equipment.id]))[equipment.id]
    holder = (await _live_holders(session, [equipment.id])).get(equipment.id)
    next_res = (await _next_reservations(session, [equipment.id], now_utc())).get(equipment.id)
    node_counts = await _node_counts(session, [equipment.id])
    detail = _row(
        equipment,
        cls,
        loc,
        access,
        counts,
        holder,
        next_res,
        node_counts.get(equipment.id, 0),
    )
    detail["class"] = class_dict(cls)
    from .grants import caller_abilities

    detail["my_abilities"] = await caller_abilities(session, identity, equipment.id, cls.id)
    return detail


async def get_by_qr(session: AsyncSession, identity: Identity, qr_token: str) -> dict:
    equipment = (
        await session.execute(select(Equipment).where(Equipment.qr_token == qr_token))
    ).scalar_one_or_none()
    if equipment is None:
        raise NotFound("equipment not found")
    return await get_equipment(session, identity, equipment.id)


async def equipment_history(
    session: AsyncSession, identity: Identity, equipment_id: uuid.UUID
) -> list[dict]:
    # reachability check
    await get_equipment(session, identity, equipment_id)
    rows = (
        (
            await session.execute(
                select(Session)
                .where(Session.equipment_id == equipment_id, Session.ended_at.is_not(None))
                .order_by(Session.started_at.desc())
            )
        )
        .scalars()
        .all()
    )
    names = await _principal_names(session, {s.user_id for s in rows})
    return [
        {
            "id": str(s.id),
            "subject": s.user_id,
            "display_name": names.get(s.user_id, s.user_id),
            "started_at": to_wire(s.started_at),
            "ended_at": to_wire(s.ended_at),
            "end_cause": s.end_cause.value if s.end_cause else None,
        }
        for s in rows
    ]


# --- Admin CRUD ---


async def create_location(session: AsyncSession, building: str, room: str) -> Location:
    loc = Location(building=building, room=room)
    session.add(loc)
    await session.flush()
    return loc


async def create_class(session: AsyncSession, **fields) -> EquipmentClass:
    cls = EquipmentClass(**fields)
    session.add(cls)
    await session.flush()
    return cls


async def create_equipment(session: AsyncSession, **fields) -> Equipment:
    fields.setdefault("qr_token", secrets.token_urlsafe(12))
    eq = Equipment(**fields)
    session.add(eq)
    await session.flush()
    return eq


async def delete_row(session: AsyncSession, obj) -> None:
    from sqlalchemy.exc import IntegrityError

    await session.delete(obj)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("record is still referenced and cannot be deleted") from exc


def effective_flags(equipment: Equipment, cls: EquipmentClass) -> dict:
    return {
        "open_access": is_open_access(equipment.open_use, cls.open_use),
        "enable_gated": is_enable_gated(equipment.requires_enable, cls.requires_enable),
    }
