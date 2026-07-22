"""Per-node authentication for the device port. The node presents its key via
`Authorization: Bearer <key>` or `X-Node-Key`. During a key rotation window the
previous key is also accepted. Any authenticated contact evidences liveness."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from ..config import get_settings
from ..errors import Unauthenticated
from ..models import InterlockNode
from ..timeutil import now_utc
from .keys import verify_key
from .rate_limit import enforce


def _extract_key(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-node-key")


def _key_matches(node: InterlockNode, key: str) -> bool:
    if verify_key(key, node.key_hash):
        return True
    if (
        node.prev_key_hash is not None
        and node.key_expiry is not None
        and now_utc() < node.key_expiry
    ):
        return verify_key(key, node.prev_key_hash)
    return False


async def authenticate_node(
    node_id: uuid.UUID, request: Request, session: AsyncSession
) -> InterlockNode:
    await enforce(node_id, get_settings().device_rate_limit_per_minute)
    node = await session.get(InterlockNode, node_id)
    key = _extract_key(request)
    if node is None or key is None or not _key_matches(node, key):
        raise Unauthenticated("node authentication failed")
    node.last_heartbeat_at = now_utc()
    node.offline = False
    await session.flush()
    return node
