"""Dual reserve/usage quotas. Reserve is checked at booking/modify (fit-check
of the full booked interval); usage is checked at Enable only (headroom > 0) and
never mid-session. Admins are exempt; users and superusers are quota'd
identically. Windows are boundary-aligned in PLATFORM_TZ."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..config import get_settings
from ..enums import QuotaType, QuotaWindow, ReservationStatus, ScopeKind
from ..errors import named_error
from ..models import QuotaPolicy, Reservation, Session
from ..timeutil import now_utc, overlap_seconds, window_bounds, window_instances
from .quota_engine import PRINCIPAL_RANK, TARGET_RANK, PolicyMatch, binding_limit

_HOUR = Decimal(3600)


def _principal_match(principal: str, subject: str, groups: set[str]) -> int | None:
    if principal == "everyone":
        return PRINCIPAL_RANK["everyone"]
    kind, _, value = principal.partition(":")
    if kind == "user" and value == subject:
        return PRINCIPAL_RANK["user"]
    if kind == "group" and value in groups:
        return PRINCIPAL_RANK["group"]
    return None


def _target_match(policy: QuotaPolicy, item_id: uuid.UUID, class_id: uuid.UUID) -> int | None:
    if policy.target_kind == ScopeKind.ITEM and policy.target_id == item_id:
        return TARGET_RANK["item"]
    if policy.target_kind == ScopeKind.CLASS and policy.target_id == class_id:
        return TARGET_RANK["class"]
    return None


async def _matching(
    session: AsyncSession,
    subject: str,
    groups: set[str],
    quota_type: QuotaType,
    item_id: uuid.UUID,
    class_id: uuid.UUID,
) -> dict[QuotaWindow, list[PolicyMatch]]:
    rows = (
        await session.execute(
            select(QuotaPolicy).where(
                QuotaPolicy.quota_type == quota_type, QuotaPolicy.active.is_(True)
            )
        )
    ).scalars()
    by_window: dict[QuotaWindow, list[PolicyMatch]] = {}
    for p in rows:
        prank = _principal_match(p.principal, subject, groups)
        trank = _target_match(p, item_id, class_id)
        if prank is None or trank is None:
            continue
        by_window.setdefault(p.window, []).append(
            PolicyMatch(prank, trank, p.limit_hours, p.hard_cap)
        )
    return by_window


def _hours(seconds: float) -> Decimal:
    return (Decimal(int(round(seconds))) / _HOUR).quantize(Decimal("0.01"))


async def reserve_consumption(
    session: AsyncSession,
    subject: str,
    window_start,
    window_end,
    exclude_id: uuid.UUID | None = None,
) -> Decimal:
    stmt = select(Reservation.starts_at, Reservation.ends_at).where(
        Reservation.user_id == subject,
        Reservation.status != ReservationStatus.CANCELLED,
        Reservation.starts_at < window_end,
        Reservation.ends_at > window_start,
    )
    if exclude_id is not None:
        stmt = stmt.where(Reservation.id != exclude_id)
    total = 0.0
    for start, end in (await session.execute(stmt)).all():
        total += overlap_seconds(start, end, window_start, window_end)
    return _hours(total)


async def usage_consumption(
    session: AsyncSession, subject: str, window_start, window_end
) -> Decimal:
    stmt = select(Session.started_at, Session.ended_at).where(
        Session.user_id == subject,
        Session.ended_at.is_not(None),
        Session.started_at < window_end,
        Session.ended_at > window_start,
    )
    total = 0.0
    for start, end in (await session.execute(stmt)).all():
        total += overlap_seconds(start, end, window_start, window_end)
    return _hours(total)


async def check_reserve_quota(
    session: AsyncSession,
    identity: Identity,
    item_id: uuid.UUID,
    class_id: uuid.UUID,
    new_start,
    new_end,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if identity.is_admin:
        return
    tz = get_settings().platform_tz
    groups = set(identity.groups)
    matches = await _matching(
        session, identity.subject, groups, QuotaType.RESERVE, item_id, class_id
    )
    for window, policies in matches.items():
        limit = binding_limit(policies)
        if limit is None:
            continue
        # Check every calendar window the new interval overlaps, not just the
        # window containing its start (a booking may straddle a boundary).
        for wstart, wend in window_instances(window.value, new_start, new_end, tz):
            consumed = await reserve_consumption(
                session, identity.subject, wstart, wend, exclude_id
            )
            consumed += _hours(overlap_seconds(new_start, new_end, wstart, wend))
            if consumed > limit:
                raise named_error(
                    "quota_exceeded",
                    details={
                        "quota_type": "reserve",
                        "window": window.value,
                        "limit_hours": str(limit),
                        "consumed_hours": str(consumed),
                    },
                )


async def check_usage_quota(
    session: AsyncSession, identity: Identity, item_id: uuid.UUID, class_id: uuid.UUID
) -> None:
    if identity.is_admin:
        return
    tz = get_settings().platform_tz
    groups = set(identity.groups)
    now = now_utc()
    matches = await _matching(session, identity.subject, groups, QuotaType.USAGE, item_id, class_id)
    for window, policies in matches.items():
        limit = binding_limit(policies)
        if limit is None:
            continue
        wstart, wend = window_bounds(window.value, now, tz)
        consumed = await usage_consumption(session, identity.subject, wstart, wend)
        if consumed >= limit:
            raise named_error(
                "quota_exceeded",
                details={
                    "quota_type": "usage",
                    "window": window.value,
                    "limit_hours": str(limit),
                    "consumed_hours": str(consumed),
                },
            )


async def quota_summary(
    session: AsyncSession, identity: Identity, item_id: uuid.UUID, class_id: uuid.UUID
) -> dict:
    tz = get_settings().platform_tz
    groups = set(identity.groups)
    now = now_utc()
    result: dict[str, list] = {"reserve": [], "usage": []}
    for qtype, key, consume in (
        (QuotaType.RESERVE, "reserve", reserve_consumption),
        (QuotaType.USAGE, "usage", usage_consumption),
    ):
        matches = await _matching(session, identity.subject, groups, qtype, item_id, class_id)
        for window in QuotaWindow:
            policies = matches.get(window, [])
            limit = None if identity.is_admin else binding_limit(policies)
            wstart, wend = window_bounds(window.value, now, tz)
            consumed = await consume(session, identity.subject, wstart, wend)
            remaining = None if limit is None else str(max(Decimal(0), limit - consumed))
            result[key].append(
                {
                    "window": window.value,
                    "limit_hours": None if limit is None else str(limit),
                    "consumed_hours": str(consumed),
                    "remaining_hours": remaining,
                }
            )
    return result
