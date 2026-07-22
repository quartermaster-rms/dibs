from __future__ import annotations

from datetime import UTC, datetime

from dibs import timeutil

TZ = "America/Los_Angeles"


def test_to_wire():
    assert timeutil.to_wire(None) is None
    assert timeutil.to_wire(datetime(2026, 7, 22, 3, 4, 5, tzinfo=UTC)) == "2026-07-22T03:04:05Z"


def test_day_window_boundary_local_midnight():
    # 2026-07-22 08:00 UTC == 2026-07-22 01:00 PDT -> day = local midnight
    at = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    start, end = timeutil.window_bounds("day", at, TZ)
    assert start == datetime(2026, 7, 22, 7, 0, tzinfo=UTC)  # 00:00 PDT
    assert end == datetime(2026, 7, 23, 7, 0, tzinfo=UTC)


def test_week_window_starts_monday():
    at = datetime(2026, 7, 22, 20, 0, tzinfo=UTC)  # a Wednesday
    start, end = timeutil.window_bounds("week", at, TZ)
    # local Monday 00:00 (2026-07-20) == 07:00 UTC
    assert start == datetime(2026, 7, 20, 7, 0, tzinfo=UTC)
    assert (end - start).days == 7


def test_dst_spring_forward_day_is_23h():
    # PST->PDT transition on 2026-03-08
    at = datetime(2026, 3, 8, 12, 0, tzinfo=UTC)
    start, end = timeutil.window_bounds("day", at, TZ)
    assert (end - start).total_seconds() / 3600 == 23


def test_window_instances_single_and_straddle():
    within = timeutil.window_instances(
        "day",
        datetime(2026, 7, 22, 18, 0, tzinfo=UTC),
        datetime(2026, 7, 22, 19, 0, tzinfo=UTC),
        TZ,
    )
    assert len(within) == 1
    # spanning local midnight -> two day windows
    straddle = timeutil.window_instances(
        "day",
        datetime(2026, 7, 23, 6, 0, tzinfo=UTC),  # 23:00 PDT (22nd)
        datetime(2026, 7, 23, 8, 0, tzinfo=UTC),  # 01:00 PDT (23rd)
        TZ,
    )
    assert len(straddle) == 2


def test_add_days_platform_dst_safe():
    at = datetime(2026, 3, 7, 20, 0, tzinfo=UTC)
    shifted = timeutil.add_days_platform(at, 1, TZ)
    # same local wall time next day, across the DST boundary
    assert shifted.astimezone(timeutil.zone(TZ)).hour == at.astimezone(timeutil.zone(TZ)).hour
