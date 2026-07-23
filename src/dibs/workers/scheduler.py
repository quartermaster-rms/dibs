"""Scheduler process: the reservation-completion sweep. No no-show or grace
sweeps; never re-evaluates a session."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import get_settings
from ..db import get_sessionmaker
from ..logging import configure_logging
from .tasks import sweep_completed


async def run_once(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        swept = await sweep_completed(session)
        await session.commit()
    return swept


async def run_forever() -> None:  # pragma: no cover - infinite loop
    settings = get_settings()
    configure_logging(f"{settings.service_name}-scheduler", settings.log_level)
    session_factory = get_sessionmaker()
    while True:
        await run_once(session_factory)
        await asyncio.sleep(settings.scheduler_interval_s)


def main() -> None:  # pragma: no cover
    asyncio.run(run_forever())


if __name__ == "__main__":  # pragma: no cover
    main()
