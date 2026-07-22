"""Interlock node provisioning endpoints (admin; surfaced on the equipment page)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_admin, require_admin_csrf
from ..auth.identity import Identity
from ..db import get_session
from ..enums import FailState
from ..services import audit, nodes

router = APIRouter()


class NodeBody(BaseModel):
    equipment_id: uuid.UUID
    name: str = ""
    fail_state: FailState
    poll_interval_s: int = Field(default=5, ge=1)
    heartbeat_interval_s: int = Field(default=30, ge=1)


class NodePatch(BaseModel):
    name: str | None = None
    fail_state: FailState | None = None
    poll_interval_s: int | None = Field(default=None, ge=1)
    heartbeat_interval_s: int | None = Field(default=None, ge=1)
    enabled: bool | None = None


@router.get("/equipment/{equipment_id}/nodes")
async def list_nodes(
    equipment_id: uuid.UUID,
    _: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await nodes.list_for_equipment(session, equipment_id)


@router.post("/nodes", status_code=201)
async def create_node(
    body: NodeBody,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    node, key = await nodes.create_node(
        session,
        body.equipment_id,
        body.name,
        body.fail_state,
        body.poll_interval_s,
        body.heartbeat_interval_s,
    )
    result = nodes.node_dict(node)
    await audit.record(
        session,
        actor=admin.subject,
        action="node.create",
        object_type="interlock_node",
        object_id=node.id,
        after=result,
    )
    return {**result, "key": key}  # one-time key, never stored in plaintext


@router.post("/nodes/{node_id}/rotate-key")
async def rotate_key(
    node_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    node, key = await nodes.rotate_key(session, node_id)
    result = nodes.node_dict(node)
    await audit.record(
        session,
        actor=admin.subject,
        action="node.rotate_key",
        object_type="interlock_node",
        object_id=node_id,
        after=result,
    )
    return {**result, "key": key}


@router.patch("/nodes/{node_id}")
async def update_node(
    node_id: uuid.UUID,
    body: NodePatch,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    node = await nodes.update_node(session, node_id, body.model_dump(exclude_unset=True))
    result = nodes.node_dict(node)
    await audit.record(
        session,
        actor=admin.subject,
        action="node.update",
        object_type="interlock_node",
        object_id=node_id,
        after=result,
    )
    return result


@router.delete("/nodes/{node_id}", status_code=204)
async def delete_node(
    node_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await nodes.delete_node(session, node_id)
    await audit.record(
        session,
        actor=admin.subject,
        action="node.delete",
        object_type="interlock_node",
        object_id=node_id,
    )
    return Response(status_code=204)
