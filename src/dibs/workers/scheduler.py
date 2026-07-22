"""Scheduler process: reservation-completion sweep and the admin daily digest.
No no-show or grace sweeps; never re-evaluates a session."""

from __future__ import annotations

import asyncio
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..cache import get_redis
from ..config import get_settings
from ..db import get_sessionmaker
from ..logging import configure_logging
from ..services.settings import get_setting
from ..timeutil import now_utc
from .tasks import send_daily_digest, sweep_completed

_DIGEST_KEY = "digest:last_sent_date"


async def run_once(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        swept = await sweep_completed(session)
        await session.commit()
    return swept


async def maybe_send_digest(session_factory: async_sessionmaker, tz: str) -> bool:
    local = now_utc().astimezone(ZoneInfo(tz))
    async with session_factory() as session:
        hour = await get_setting(session, "digest_hour_local")
        if local.hour < hour:
            return False
        redis = get_redis()
        today = local.date().isoformat()
        if await redis.get(_DIGEST_KEY) == today:
            return False
        await send_daily_digest(session)
        await session.commit()
        await redis.set(_DIGEST_KEY, today)
        return True


async def run_forever() -> None:  # pragma: no cover - infinite loop
    settings = get_settings()
    configure_logging(f"{settings.service_name}-scheduler", settings.log_level)
    session_factory = get_sessionmaker()
    while True:
        await run_once(session_factory)
        await maybe_send_digest(session_factory, settings.platform_tz)
        await asyncio.sleep(settings.scheduler_interval_s)


def main() -> None:  # pragma: no cover
    asyncio.run(run_forever())


if __name__ == "__main__":  # pragma: no cover
    main()
