"""Worker process: node-offline detection, background notification dispatch, and
optional MQTT desired-state publishing. Never re-evaluates a session."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import get_settings
from ..db import get_sessionmaker
from ..logging import configure_logging
from ..models import InterlockNode, Session
from .mqtt import MqttPublisher
from .tasks import detect_offline


async def publish_desired_states(session, mqtt: MqttPublisher) -> None:
    if not mqtt.enabled:
        return
    live = {
        eq_id
        for (eq_id,) in (
            await session.execute(select(Session.equipment_id).where(Session.ended_at.is_(None)))
        ).all()
    }
    nodes = (await session.execute(select(InterlockNode))).scalars().all()
    for node in nodes:
        mqtt.publish_state(node.id, node.equipment_id in live)


async def run_once(session_factory: async_sessionmaker, mqtt: MqttPublisher) -> None:
    async with session_factory() as session:
        await detect_offline(session)
        await publish_desired_states(session, mqtt)
        await session.commit()


async def run_forever() -> None:  # pragma: no cover - infinite loop
    settings = get_settings()
    configure_logging(f"{settings.service_name}-worker", settings.log_level)
    mqtt = MqttPublisher(settings)
    mqtt.connect()
    session_factory = get_sessionmaker()
    while True:
        await run_once(session_factory, mqtt)
        await asyncio.sleep(settings.worker_interval_s)


def main() -> None:  # pragma: no cover
    asyncio.run(run_forever())


if __name__ == "__main__":  # pragma: no cover
    main()
