from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from tests.factories import (
    make_equipment,
    make_issue,
    make_node,
    make_reservation,
    make_session,
)

from dibs.config import Settings
from dibs.db import get_sessionmaker
from dibs.enums import ReservationStatus, Severity
from dibs.models import Principal
from dibs.services.notifications import list_for
from dibs.services.settings import set_setting
from dibs.workers import scheduler, tasks, worker
from dibs.workers.mqtt import MqttPublisher


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


def test_mqtt_dormant():
    pub = MqttPublisher(Settings(auth_mode="stub"))
    assert pub.enabled is False
    pub.publish_state(uuid.uuid4(), True)  # no-op


def test_mqtt_publish_payload():
    pub = MqttPublisher(Settings(auth_mode="stub", mqtt_url="mqtts://broker:8883"))
    assert pub.enabled is True

    class Fake:
        def __init__(self):
            self.calls = []

        def publish(self, topic, payload, qos, retain):
            self.calls.append((topic, payload))

    pub._client = Fake()
    nid = uuid.uuid4()
    pub.publish_state(nid, True)
    assert pub._client.calls[0][0] == f"dibs/nodes/{nid}/desired"
    assert '"enabled": true' in pub._client.calls[0][1]


async def test_worker_run_once(db_session):
    eq = await make_equipment(db_session)
    await make_node(db_session, eq.id)
    await db_session.commit()
    await worker.run_once(get_sessionmaker(), MqttPublisher(Settings(auth_mode="stub")))


async def test_worker_publishes_desired_states(db_session):
    eq = await make_equipment(db_session)
    await make_node(db_session, eq.id)
    await make_session(db_session, eq.id, "u", datetime.now(UTC))
    await db_session.commit()
    pub = MqttPublisher(Settings(auth_mode="stub", mqtt_url="mqtts://b:8883"))

    class Fake:
        def __init__(self):
            self.calls = []

        def publish(self, topic, payload, qos, retain):
            self.calls.append((topic, payload))

    pub._client = Fake()
    async with get_sessionmaker()() as session:
        await worker.publish_desired_states(session, pub)
    assert len(pub._client.calls) == 1 and '"enabled": true' in pub._client.calls[0][1]


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
