"""The unit-of-work functions the worker and scheduler run each tick."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import ReservationStatus
from ..metrics import NODE_OFFLINE
from ..models import InterlockNode, Reservation
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


async def detect_offline(session: AsyncSession, now: datetime | None = None) -> list[uuid.UUID]:
    """Mark nodes offline after several missed heartbeats. Pure monitoring —
    never alters a session."""
    now = now or now_utc()
    misses = await get_setting(session, "node_offline_missed_heartbeats")
    nodes = (
        (await session.execute(select(InterlockNode).where(InterlockNode.offline.is_(False))))
        .scalars()
        .all()
    )
    newly: list[uuid.UUID] = []
    for node in nodes:
        reference = node.last_heartbeat_at or node.created_at
        if (now - reference).total_seconds() > node.heartbeat_interval_s * misses:
            node.offline = True
            newly.append(node.id)
            NODE_OFFLINE.inc()
    await session.flush()
    return newly
