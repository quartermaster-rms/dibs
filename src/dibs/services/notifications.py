"""Per-recipient in-app notification inbox."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import NotFound
from ..models import Notification
from ..timeutil import now_utc, to_wire


def _dict(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "body": n.body,
        "read_at": to_wire(n.read_at),
        "created_at": to_wire(n.created_at),
    }


async def notify(session: AsyncSession, recipient: str, body: str) -> Notification:
    n = Notification(recipient=recipient, body=body)
    session.add(n)
    await session.flush()
    return n


async def list_for(session: AsyncSession, recipient: str, unread_only: bool = False) -> list[dict]:
    stmt = select(Notification).where(Notification.recipient == recipient)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc())
    return [_dict(n) for n in (await session.execute(stmt)).scalars()]


async def mark_read(session: AsyncSession, recipient: str, notification_id: uuid.UUID) -> dict:
    n = await session.get(Notification, notification_id)
    if n is None or n.recipient != recipient:
        raise NotFound("notification not found")
    if n.read_at is None:
        n.read_at = now_utc()
        await session.flush()
    return _dict(n)
