"""Interlock node provisioning (admin, on the equipment page). A node links to
exactly one enable-gated item; the one-time key is returned once and stored
hashed."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..device.keys import generate_key, hash_key
from ..enums import FailState
from ..errors import NotFound, named_error
from ..models import Equipment, EquipmentClass, InterlockNode
from ..permissions.tiers import is_enable_gated
from ..timeutil import now_utc, to_wire
from .settings import get_setting


def node_dict(n: InterlockNode) -> dict:
    return {
        "id": str(n.id),
        "equipment_id": str(n.equipment_id),
        "name": n.name,
        "fail_state": n.fail_state.value,
        "poll_interval_s": n.poll_interval_s,
        "heartbeat_interval_s": n.heartbeat_interval_s,
        "enabled": n.enabled,
        "offline": n.offline,
        "last_heartbeat_at": to_wire(n.last_heartbeat_at),
        "last_firmware": n.last_firmware,
        "key_expiry": to_wire(n.key_expiry),
        "has_prev_key": n.prev_key_hash is not None,
    }


async def _require_enable_gated(session: AsyncSession, equipment_id: uuid.UUID) -> None:
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise NotFound("equipment not found")
    klass = cast(EquipmentClass, await session.get(EquipmentClass, equipment.class_id))
    if not is_enable_gated(equipment.requires_enable, klass.requires_enable):
        raise named_error("enable_not_supported", "equipment is not enable-gated")


async def create_node(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    name: str,
    fail_state: FailState,
    poll_interval_s: int,
    heartbeat_interval_s: int,
) -> tuple[InterlockNode, str]:
    await _require_enable_gated(session, equipment_id)
    key = generate_key()
    node = InterlockNode(
        equipment_id=equipment_id,
        name=name,
        fail_state=fail_state,
        poll_interval_s=poll_interval_s,
        heartbeat_interval_s=heartbeat_interval_s,
        key_hash=hash_key(key),
    )
    session.add(node)
    await session.flush()
    return node, key


async def get_node(session: AsyncSession, node_id: uuid.UUID) -> InterlockNode:
    node = await session.get(InterlockNode, node_id)
    if node is None:
        raise NotFound("node not found")
    return node


async def rotate_key(session: AsyncSession, node_id: uuid.UUID) -> tuple[InterlockNode, str]:
    node = await get_node(session, node_id)
    key = generate_key()
    node.prev_key_hash = node.key_hash
    node.key_hash = hash_key(key)
    grace = await get_setting(session, "key_rotation_grace_hours")
    node.key_expiry = now_utc() + timedelta(hours=grace)
    await session.flush()
    return node, key


async def update_node(session: AsyncSession, node_id: uuid.UUID, fields: dict) -> InterlockNode:
    node = await get_node(session, node_id)
    for key, value in fields.items():
        setattr(node, key, value)
    await session.flush()
    return node


async def delete_node(session: AsyncSession, node_id: uuid.UUID) -> None:
    node = await get_node(session, node_id)
    await session.delete(node)
    await session.flush()


async def list_for_equipment(session: AsyncSession, equipment_id: uuid.UUID) -> list[dict]:
    rows = (
        await session.execute(
            select(InterlockNode)
            .where(InterlockNode.equipment_id == equipment_id)
            .order_by(InterlockNode.created_at)
        )
    ).scalars()
    return [node_dict(n) for n in rows]
