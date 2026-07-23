"""Worker process: node-offline detection and background notification dispatch.
Never re-evaluates a session."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import get_settings
from ..db import get_sessionmaker
from ..logging import configure_logging
from .tasks import detect_offline


async def run_once(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        await detect_offline(session)
        await session.commit()


async def run_forever() -> None:  # pragma: no cover - infinite loop
    settings = get_settings()
    configure_logging(f"{settings.service_name}-worker", settings.log_level)
    session_factory = get_sessionmaker()
    while True:
        await run_once(session_factory)
        await asyncio.sleep(settings.worker_interval_s)


def main() -> None:  # pragma: no cover
    asyncio.run(run_forever())


if __name__ == "__main__":  # pragma: no cover
    main()
