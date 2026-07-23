from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.factories import (
    make_equipment,
    make_issue,
    make_node,
    make_reservation,
    make_session,
)

from dibs.db import get_sessionmaker
from dibs.enums import ReservationStatus, Severity
from dibs.models import Principal
from dibs.services.notifications import list_for
from dibs.services.settings import set_setting
from dibs.workers import scheduler, tasks, worker


async def _admin(db_session, subject="admin1"):
    db_session.add(Principal(subject=subject, display_name="A", email="a@x", is_admin=True))
    await db_session.flush()


async def test_sweep_completed(db_session):
    eq = await make_equipment(db_session)
    now = datetime.now(UTC)
    past = await make_reservation(
        db_session, eq.id, "u", now - timedelta(hours=2), now - timedelta(hours=1)
    )
    future = await make_reservation(
        db_session, eq.id, "u", now + timedelta(days=1), now + timedelta(days=1, hours=1)
    )
    await db_session.commit()
    assert await tasks.sweep_completed(db_session) == 1
    await db_session.commit()
    await db_session.refresh(past)
    await db_session.refresh(future)
    assert past.status == ReservationStatus.COMPLETED
    assert future.status == ReservationStatus.BOOKED


async def test_detect_offline_notifies_admins(db_session):
    await _admin(db_session)
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id)
    node.last_heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()
    newly = await tasks.detect_offline(db_session)
    await db_session.commit()
    assert node.id in newly
    await db_session.refresh(node)
    assert node.offline is True
    assert any("offline" in n["body"] for n in await list_for(db_session, "admin1"))
    # already offline -> not re-detected
    assert await tasks.detect_offline(db_session) == []


async def test_daily_digest(db_session):
    await _admin(db_session)
    eq = await make_equipment(db_session)
    await make_issue(db_session, eq.id, severity=Severity.FATAL)
    await make_session(db_session, eq.id, "u", datetime.now(UTC))
    await db_session.commit()
    digest = await tasks.send_daily_digest(db_session)
    await db_session.commit()
    assert digest["open_issues"] == 1 and digest["red_equipment"] == 1
    assert digest["active_sessions"] == 1
    assert any("Daily digest" in n["body"] for n in await list_for(db_session, "admin1"))


async def test_worker_run_once(db_session):
    eq = await make_equipment(db_session)
    await make_node(db_session, eq.id)
    await db_session.commit()
    await worker.run_once(get_sessionmaker())


async def test_scheduler_run_once(db_session):
    eq = await make_equipment(db_session)
    now = datetime.now(UTC)
    await make_reservation(
        db_session, eq.id, "u", now - timedelta(hours=2), now - timedelta(hours=1)
    )
    await db_session.commit()
    assert await scheduler.run_once(get_sessionmaker()) == 1


async def test_scheduler_digest_once_per_day(db_session):
    await _admin(db_session)
    await set_setting(db_session, "digest_hour_local", 0)
    await db_session.commit()
    sent1 = await scheduler.maybe_send_digest(get_sessionmaker(), "America/Los_Angeles")
    sent2 = await scheduler.maybe_send_digest(get_sessionmaker(), "America/Los_Angeles")
    assert sent1 is True and sent2 is False
