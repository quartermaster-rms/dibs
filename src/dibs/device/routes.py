"""Device endpoints: desired-state polling and heartbeat."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Session
from ..services.settings import get_setting
from ..timeutil import to_wire
from .auth import authenticate_node

router = APIRouter()


class HeartbeatBody(BaseModel):
    firmware: str | None = None


async def _live_session(session: AsyncSession, equipment_id: uuid.UUID) -> Session | None:
    return (
        await session.execute(
            select(Session).where(Session.equipment_id == equipment_id, Session.ended_at.is_(None))
        )
    ).scalar_one_or_none()


@router.get("/device/nodes/{node_id}/desired-state")
async def desired_state(
    node_id: uuid.UUID, request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    node = await authenticate_node(node_id, request, session)
    live = await _live_session(session, node.equipment_id)
    multiplier = await get_setting(session, "desired_state_ttl_multiplier")
    context = (
        {
            "session_id": str(live.id),
            "user_id": live.user_id,
            "started_at": to_wire(live.started_at),
        }
        if live is not None
        else None
    )
    return {
        "enabled": live is not None,
        "ttl_seconds": node.poll_interval_s * multiplier,
        "context": context,
    }


@router.post("/device/nodes/{node_id}/heartbeat")
async def heartbeat(
    node_id: uuid.UUID,
    body: HeartbeatBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    node = await authenticate_node(node_id, request, session)
    if body.firmware is not None:
        node.last_firmware = body.firmware
        await session.flush()
    return {"ok": True}
