"""People directory (dibs-known users) and admin analytics/audit queries."""

from __future__ import annotations

import base64
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import rows_to_dict
from ..enums import ReservationStatus, ScopeKind, Tier
from ..models import Audit, Equipment, EquipmentClass, Principal, Reservation, RoleGrant, Session
from ..timeutil import now_utc, overlap_seconds, to_wire


async def list_people(session: AsyncSession) -> list[dict]:
    principals = (
        (await session.execute(select(Principal).order_by(Principal.display_name))).scalars().all()
    )
    grants = (
        (
            await session.execute(
                select(RoleGrant).where(RoleGrant.tier.in_((Tier.USER, Tier.SUPERUSER)))
            )
        )
        .scalars()
        .all()
    )
    eq_names = rows_to_dict(await session.execute(select(Equipment.id, Equipment.name)))
    cls_names = rows_to_dict(await session.execute(select(EquipmentClass.id, EquipmentClass.name)))
    by_subject: dict[str, list] = defaultdict(list)
    for g in grants:
        name = (
            eq_names.get(g.scope_id)
            if g.scope_kind == ScopeKind.ITEM
            else cls_names.get(g.scope_id)
        )
        by_subject[g.subject].append(
            {
                "scope_kind": g.scope_kind.value,
                "scope_id": str(g.scope_id),
                "scope_name": name,
                "tier": g.tier.value,
            }
        )
    result = []
    for p in principals:
        result.append(
            {
                "subject": p.subject,
                "display_name": p.display_name,
                "email": p.email,
                "is_admin": p.is_admin,
                "standing": "admin" if p.is_admin else "user",
                "grants": [] if p.is_admin else by_subject.get(p.subject, []),
            }
        )
    return result


async def utilization(
    session: AsyncSession,
    class_id: uuid.UUID | None,
    from_: datetime | None,
    to: datetime | None,
) -> dict:
    to = to or now_utc()
    from_ = from_ or now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    eq_stmt = select(Equipment.id, Equipment.name)
    if class_id is not None:
        eq_stmt = eq_stmt.where(Equipment.class_id == class_id)
    equipment = list((await session.execute(eq_stmt)).all())
    eq_ids = [e[0] for e in equipment]
    used: dict[uuid.UUID, float] = defaultdict(float)
    counts: dict[uuid.UUID, int] = defaultdict(int)
    reserved: dict[uuid.UUID, float] = defaultdict(float)
    if eq_ids:
        for eq_id, s_start, s_end in (
            await session.execute(
                select(Session.equipment_id, Session.started_at, Session.ended_at).where(
                    Session.equipment_id.in_(eq_ids),
                    Session.ended_at.is_not(None),
                    Session.started_at < to,
                    Session.ended_at > from_,
                )
            )
        ).all():
            used[eq_id] += overlap_seconds(s_start, s_end, from_, to) / 3600
            counts[eq_id] += 1
        for eq_id, r_start, r_end in (
            await session.execute(
                select(Reservation.equipment_id, Reservation.starts_at, Reservation.ends_at).where(
                    Reservation.equipment_id.in_(eq_ids),
                    Reservation.status != ReservationStatus.CANCELLED,
                    Reservation.starts_at < to,
                    Reservation.ends_at > from_,
                )
            )
        ).all():
            reserved[eq_id] += overlap_seconds(r_start, r_end, from_, to) / 3600
    window_hours = max(0.0, (to - from_).total_seconds() / 3600)
    return {
        "from": to_wire(from_),
        "to": to_wire(to),
        "window_hours": round(window_hours, 2),
        "equipment": [
            {
                "equipment_id": str(eq_id),
                "name": name,
                "used_hours": round(used[eq_id], 2),
                "reserved_hours": round(reserved[eq_id], 2),
                "session_count": counts[eq_id],
                "utilization": round(used[eq_id] / window_hours, 4) if window_hours else 0.0,
            }
            for eq_id, name in equipment
        ],
    }


def _encode_cursor(ts: datetime, row_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{row_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts_str, id_str = raw.split("|")
    return datetime.fromisoformat(ts_str), uuid.UUID(id_str)


async def list_audit(
    session: AsyncSession,
    *,
    actor: str | None,
    action: str | None,
    object_type: str | None,
    object_id: str | None,
    from_: datetime | None,
    to: datetime | None,
    limit: int,
    cursor: str | None,
) -> dict:
    stmt = select(Audit)
    if actor:
        stmt = stmt.where(Audit.actor == actor)
    if action:
        stmt = stmt.where(Audit.action == action)
    if object_type:
        stmt = stmt.where(Audit.object_type == object_type)
    if object_id:
        stmt = stmt.where(Audit.object_id == object_id)
    if from_:
        stmt = stmt.where(Audit.ts >= from_)
    if to:
        stmt = stmt.where(Audit.ts < to)
    if cursor:
        c_ts, c_id = _decode_cursor(cursor)
        stmt = stmt.where(or_(Audit.ts < c_ts, and_(Audit.ts == c_ts, Audit.id < c_id)))
    stmt = stmt.order_by(Audit.ts.desc(), Audit.id.desc()).limit(limit + 1)
    rows = (await session.execute(stmt)).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.ts, last.id)
        rows = rows[:limit]
    items = [
        {
            "id": str(a.id),
            "ts": to_wire(a.ts),
            "actor": a.actor,
            "action": a.action,
            "object_type": a.object_type,
            "object_id": a.object_id,
            "before": a.before,
            "after": a.after,
            "request_id": a.request_id,
        }
        for a in rows
    ]
    return {"items": items, "next_cursor": next_cursor}
