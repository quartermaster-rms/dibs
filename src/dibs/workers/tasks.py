"""The unit-of-work functions the worker and scheduler run each tick."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import IssueStatus, ReservationStatus, Severity
from ..metrics import NODE_OFFLINE
from ..models import Equipment, InterlockNode, IssueReport, Principal, Reservation, Session
from ..services.notifications import notify
from ..services.settings import get_setting
from ..timeutil import now_utc


async def sweep_completed(session: AsyncSession, now: datetime | None = None) -> int:
    """Mark booked reservations whose window has ended as completed. Never
    touches sessions or cancelled rows."""
    now = now or now_utc()
    result = await session.execute(
        update(Reservation)
        .where(Reservation.status == ReservationStatus.BOOKED, Reservation.ends_at <= now)
        .values(status=ReservationStatus.COMPLETED)
    )
    return cast(int, result.rowcount)  # type: ignore[attr-defined]


async def admin_subjects(session: AsyncSession) -> list[str]:
    return [
        s
        for (s,) in (
            await session.execute(select(Principal.subject).where(Principal.is_admin.is_(True)))
        ).all()
    ]


async def detect_offline(session: AsyncSession, now: datetime | None = None) -> list[uuid.UUID]:
    """Mark nodes offline after several missed heartbeats; notify admins. Pure
    monitoring — never alters a session."""
    now = now or now_utc()
    misses = await get_setting(session, "node_offline_missed_heartbeats")
    nodes = (
        (await session.execute(select(InterlockNode).where(InterlockNode.offline.is_(False))))
        .scalars()
        .all()
    )
    admins: list[str] | None = None
    newly: list[uuid.UUID] = []
    for node in nodes:
        reference = node.last_heartbeat_at or node.created_at
        if (now - reference).total_seconds() > node.heartbeat_interval_s * misses:
            node.offline = True
            newly.append(node.id)
            NODE_OFFLINE.inc()
            if admins is None:
                admins = await admin_subjects(session)
            equipment = cast(Equipment, await session.get(Equipment, node.equipment_id))
            for admin in admins:
                await notify(
                    session, admin, f"Interlock node '{node.name}' on {equipment.name} is offline."
                )
    await session.flush()
    return newly


async def _count(session: AsyncSession, stmt) -> int:
    return (await session.execute(stmt)).scalar_one()


async def build_digest(session: AsyncSession) -> dict:
    open_issues = await _count(
        session,
        select(func.count()).select_from(IssueReport).where(IssueReport.status == IssueStatus.OPEN),
    )
    red_equipment = await _count(
        session,
        select(func.count(func.distinct(IssueReport.equipment_id))).where(
            IssueReport.status == IssueStatus.OPEN, IssueReport.severity == Severity.FATAL
        ),
    )
    active_sessions = await _count(
        session, select(func.count()).select_from(Session).where(Session.ended_at.is_(None))
    )
    upcoming = await _count(
        session,
        select(func.count())
        .select_from(Reservation)
        .where(Reservation.status == ReservationStatus.BOOKED, Reservation.starts_at > now_utc()),
    )
    return {
        "open_issues": open_issues,
        "red_equipment": red_equipment,
        "active_sessions": active_sessions,
        "upcoming_reservations": upcoming,
    }


async def send_daily_digest(session: AsyncSession) -> dict:
    digest = await build_digest(session)
    body = (
        f"Daily digest — {digest['open_issues']} open issues, "
        f"{digest['red_equipment']} out of service, "
        f"{digest['active_sessions']} active sessions, "
        f"{digest['upcoming_reservations']} upcoming reservations."
    )
    for admin in await admin_subjects(session):
        await notify(session, admin, body)
    await session.flush()
    return digest
