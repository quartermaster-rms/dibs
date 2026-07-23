"""Enable / Disable and the overriding safety kernel. A running session is NEVER
ended automatically — only a deliberate manual Disable (the holder ending their
own, or an admin force-closing another's) ends it. Enable is decoupled from
reservations and never touches them."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..enums import EndCause, IssueStatus, Severity
from ..errors import Conflict, Forbidden, named_error
from ..models import InterlockNode, IssueReport, Session
from ..permissions.access import load_access
from ..timeutil import now_utc, to_wire
from .quotas import check_usage_quota


def _session_dict(s: Session) -> dict:
    return {
        "id": str(s.id),
        "equipment_id": str(s.equipment_id),
        "user_id": s.user_id,
        "started_at": to_wire(s.started_at),
        "ended_at": to_wire(s.ended_at),
        "end_cause": s.end_cause.value if s.end_cause else None,
    }


async def _live_session(session: AsyncSession, equipment_id: uuid.UUID) -> Session | None:
    return (
        await session.execute(
            select(Session).where(Session.equipment_id == equipment_id, Session.ended_at.is_(None))
        )
    ).scalar_one_or_none()


async def _any_node_disabled(session: AsyncSession, equipment_id: uuid.UUID) -> bool:
    return (
        await session.execute(
            select(InterlockNode.id).where(
                InterlockNode.equipment_id == equipment_id,
                InterlockNode.enabled.is_(False),
            )
        )
    ).first() is not None


async def _has_open_fatal(session: AsyncSession, equipment_id: uuid.UUID) -> bool:
    return (
        await session.execute(
            select(IssueReport.id).where(
                IssueReport.equipment_id == equipment_id,
                IssueReport.status == IssueStatus.OPEN,
                IssueReport.severity == Severity.FATAL,
            )
        )
    ).first() is not None


async def enable(
    session: AsyncSession, identity: Identity, equipment_id: uuid.UUID
) -> tuple[dict, bool]:
    """Returns (session, created). Re-Enable by the same holder is idempotent."""
    access = await load_access(session, identity, equipment_id)
    if not access.enable_gated:
        raise named_error("enable_not_supported")
    if not access.can_operate:
        raise Forbidden("you are not authorized to enable this equipment")

    live = await _live_session(session, equipment_id)
    if live is not None:
        if live.user_id == identity.subject:
            return _session_dict(live), False  # idempotent; not re-blocked by red/quota
        raise named_error("equipment_in_use", details={"holder": live.user_id})

    if await _any_node_disabled(session, equipment_id):
        raise named_error("node_disabled")
    if await _has_open_fatal(session, equipment_id) and not identity.is_admin:
        raise named_error("fatal_fault_open")
    await check_usage_quota(session, identity, equipment_id, access.class_id)

    new = Session(equipment_id=equipment_id, user_id=identity.subject, started_at=now_utc())
    session.add(new)
    try:
        await session.flush()
    except IntegrityError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == "23505":
            raise named_error("equipment_in_use") from exc
        raise
    return _session_dict(new), True


async def disable(session: AsyncSession, identity: Identity, equipment_id: uuid.UUID) -> dict:
    live = await _live_session(session, equipment_id)
    if live is None:
        raise Conflict("no active session on this equipment", code="no_active_session")
    is_holder = live.user_id == identity.subject
    if is_holder:
        cause = EndCause.USER
    elif identity.is_admin:
        cause = EndCause.ADMIN
    else:
        raise Forbidden("only the holder or an admin may end this session")
    live.ended_at = now_utc()
    live.end_cause = cause
    await session.flush()
    return _session_dict(live)
