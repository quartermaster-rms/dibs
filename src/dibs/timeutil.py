"""UTC-on-the-wire, PLATFORM_TZ-for-calendar time helpers (IMPLEMENTATION-GUIDE §1).

Calendar periods are boundary-aligned in ``PLATFORM_TZ`` (day = local midnight,
week = local Monday 00:00, month = local 1st 00:00), never rolling, and DST-safe.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

WindowKind = Literal["day", "week", "month"]


def now_utc() -> datetime:
    return datetime.now(UTC)


def zone(tz: str) -> ZoneInfo:
    return ZoneInfo(tz)


def _local_midnight(d: date, z: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=z)


def window_bounds(kind: WindowKind, at: datetime, tz: str) -> tuple[datetime, datetime]:
    """Return [start, end) in UTC for the calendar window containing ``at``."""
    z = zone(tz)
    local = at.astimezone(z)
    d = local.date()
    if kind == "day":
        start = _local_midnight(d, z)
        end = _local_midnight(d + timedelta(days=1), z)
    elif kind == "week":
        monday = d - timedelta(days=local.weekday())
        start = _local_midnight(monday, z)
        end = _local_midnight(monday + timedelta(days=7), z)
    else:  # month
        first = d.replace(day=1)
        start = _local_midnight(first, z)
        nxt = (
            date(first.year + 1, 1, 1)
            if first.month == 12
            else date(first.year, first.month + 1, 1)
        )
        end = _local_midnight(nxt, z)
    return start.astimezone(UTC), end.astimezone(UTC)


def add_days_platform(at: datetime, days: int, tz: str) -> datetime:
    """``at`` shifted by whole calendar days in PLATFORM_TZ, DST-safe, back to UTC."""
    z = zone(tz)
    local = at.astimezone(z)
    shifted = datetime.combine((local.date() + timedelta(days=days)), local.time(), tzinfo=z)
    return shifted.astimezone(UTC)


def overlap_seconds(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> float:
    """Seconds of overlap between [a_start,a_end) and [b_start,b_end)."""
    lo = max(a_start, b_start)
    hi = min(a_end, b_end)
    return max(0.0, (hi - lo).total_seconds())
