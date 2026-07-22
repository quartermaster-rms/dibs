"""Per-node fixed-window rate limiting on the device port (Redis-backed)."""

from __future__ import annotations

import uuid

from ..cache import get_redis
from ..errors import RateLimited


async def enforce(node_id: uuid.UUID, limit_per_minute: int) -> None:
    key = f"devrate:{node_id}"
    redis = get_redis()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > limit_per_minute:
        raise RateLimited("device request rate exceeded", code="rate_limited")
