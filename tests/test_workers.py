from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.factories import make_equipment, make_node, make_reservation

from dibs.db import get_sessionmaker
from dibs.enums import ReservationStatus
from dibs.workers import scheduler, tasks, worker


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


async def test_detect_offline(db_session):
    eq = await make_equipment(db_session)
    node = await make_node(db_session, eq.id)
    node.last_heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()
    newly = await tasks.detect_offline(db_session)
    await db_session.commit()
    assert node.id in newly
    await db_session.refresh(node)
    assert node.offline is True
    # already offline -> not re-detected
    assert await tasks.detect_offline(db_session) == []


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
