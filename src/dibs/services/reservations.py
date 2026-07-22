"""Reservations: good-faith calendar coordination, fully detached from Enable.
15-min-granularity (configurable), exclusivity over non-cancelled rows, cancel/
move/resize strictly before starts_at, no on-behalf/impersonation, reserve-quota
fit-check. dibs never auto-frees a slot and never touches a session."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..config import get_settings
from ..db import rows_to_dict
from ..enums import ReservationStatus
from ..errors import Forbidden, NotFound, ValidationFailed, named_error
from ..models import Principal, Reservation
from ..permissions.access import load_access, require_reachable
from ..timeutil import add_days_platform, now_utc, to_wire
from .settings import get_setting


def _res_dict(r: Reservation, display_name: str | None = None) -> dict:
    return {
        "id": str(r.id),
        "equipment_id": str(r.equipment_id),
        "user_id": r.user_id,
        "created_by": r.created_by,
        "display_name": display_name,
        "starts_at": to_wire(r.starts_at),
        "ends_at": to_wire(r.ends_at),
        "status": r.status.value,
    }


def _ensure_utc(dt: datetime, field: str) -> datetime:
    if dt.tzinfo is None:
        raise ValidationFailed(f"{field} must be timezone-aware", code="naive_datetime")
    return dt.astimezone(UTC)


def _aligned(dt: datetime, granularity: int, tz: str) -> bool:
    local = dt.astimezone(ZoneInfo(tz))
    return local.second == 0 and local.microsecond == 0 and local.minute % granularity == 0


async def _validate_window(session: AsyncSession, starts_at: datetime, ends_at: datetime) -> None:
    granularity = await get_setting(session, "reservation_slot_granularity_minutes")
    max_days = await get_setting(session, "max_reservation_days_advance")
    tz = get_settings().platform_tz
    if ends_at <= starts_at:
        raise ValidationFailed("ends_at must be after starts_at", code="invalid_interval")
    if not _aligned(starts_at, granularity, tz) or not _aligned(ends_at, granularity, tz):
        raise named_error("slot_misaligned", details={"granularity_minutes": granularity})
    if starts_at <= now_utc():
        raise named_error("starts_in_past")
    latest = add_days_platform(now_utc(), max_days, tz)
    if starts_at > latest:
        raise named_error("advance_limit_exceeded", details={"max_days": max_days})


async def _flush(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == "23P01":
            raise named_error("reservation_conflict") from exc
        raise


async def create_reservation(
    session: AsyncSession,
    identity: Identity,
    equipment_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> dict:
    starts_at = _ensure_utc(starts_at, "starts_at")
    ends_at = _ensure_utc(ends_at, "ends_at")
    access = await load_access(session, identity, equipment_id)
    if not access.can_operate:
        raise Forbidden("you are not authorized to reserve this equipment")
    await _validate_window(session, starts_at, ends_at)
    from .quotas import check_reserve_quota

    await check_reserve_quota(session, identity, equipment_id, access.class_id, starts_at, ends_at)
    res = Reservation(
        equipment_id=equipment_id,
        user_id=identity.subject,
        created_by=identity.subject,
        starts_at=starts_at,
        ends_at=ends_at,
        status=ReservationStatus.BOOKED,
    )
    session.add(res)
    await _flush(session)
    return _res_dict(res)


async def modify_reservation(
    session: AsyncSession,
    identity: Identity,
    reservation_id: uuid.UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> dict:
    starts_at = _ensure_utc(starts_at, "starts_at")
    ends_at = _ensure_utc(ends_at, "ends_at")
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise NotFound("reservation not found")
    if res.user_id != identity.subject:
        raise Forbidden("you may only modify your own reservations")
    if res.status != ReservationStatus.BOOKED or res.starts_at <= now_utc():
        raise named_error("reservation_immutable")
    access = await load_access(session, identity, res.equipment_id)
    if not access.can_operate:
        raise Forbidden("you are not authorized to reserve this equipment")
    await _validate_window(session, starts_at, ends_at)
    from .quotas import check_reserve_quota

    await check_reserve_quota(
        session,
        identity,
        res.equipment_id,
        access.class_id,
        starts_at,
        ends_at,
        exclude_id=res.id,
    )
    res.starts_at = starts_at
    res.ends_at = ends_at
    await _flush(session)
    return _res_dict(res)


async def cancel_reservation(
    session: AsyncSession, identity: Identity, reservation_id: uuid.UUID
) -> dict:
    res = await session.get(Reservation, reservation_id)
    if res is None:
        raise NotFound("reservation not found")
    if res.user_id != identity.subject and not identity.is_admin:
        raise Forbidden("only an admin may cancel another user's reservation")
    if res.status == ReservationStatus.CANCELLED:
        return _res_dict(res)
    if res.starts_at <= now_utc():
        raise named_error("reservation_immutable")
    res.status = ReservationStatus.CANCELLED
    await session.flush()
    return _res_dict(res)


async def list_for_equipment(
    session: AsyncSession,
    identity: Identity,
    equipment_id: uuid.UUID,
    from_: datetime | None,
    to: datetime | None,
) -> list[dict]:
    await require_reachable(session, identity, equipment_id)
    stmt = select(Reservation).where(
        Reservation.equipment_id == equipment_id,
        Reservation.status != ReservationStatus.CANCELLED,
    )
    if from_ is not None:
        stmt = stmt.where(Reservation.ends_at > _ensure_utc(from_, "from"))
    if to is not None:
        stmt = stmt.where(Reservation.starts_at < _ensure_utc(to, "to"))
    stmt = stmt.order_by(Reservation.starts_at)
    rows = (await session.execute(stmt)).scalars().all()
    names = await _names(session, {r.user_id for r in rows})
    return [_res_dict(r, names.get(r.user_id)) for r in rows]


async def list_mine(session: AsyncSession, identity: Identity) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(Reservation)
                .where(
                    Reservation.user_id == identity.subject,
                    Reservation.status != ReservationStatus.CANCELLED,
                )
                .order_by(Reservation.starts_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_res_dict(r) for r in rows]


async def _names(session: AsyncSession, subjects: set[str]) -> dict[str, str]:
    if not subjects:
        return {}
    rows = await session.execute(
        select(Principal.subject, Principal.display_name).where(Principal.subject.in_(subjects))
    )
    return rows_to_dict(rows)
