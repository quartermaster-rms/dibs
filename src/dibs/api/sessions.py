"""Enable / Disable endpoints (enable-gated equipment only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..db import get_session
from ..permissions.deps import require_dibs_access_csrf
from ..services import audit, sessions
from ..services.idempotency import Idempotency

router = APIRouter()


@router.post("/equipment/{equipment_id}/enable")
async def enable_equipment(
    equipment_id: uuid.UUID,
    request: Request,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    idem = Idempotency(session, identity.subject, request)
    replay = await idem.replay()
    if replay is not None:
        return replay
    result, created = await sessions.enable(session, identity, equipment_id)
    if created:
        await audit.record(
            session,
            actor=identity.subject,
            action="session.enable",
            object_type="session",
            object_id=result["id"],
            after=result,
        )
    return await idem.store(201 if created else 200, result)


@router.post("/equipment/{equipment_id}/disable")
async def disable_equipment(
    equipment_id: uuid.UUID,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await sessions.disable(session, identity, equipment_id)
    await audit.record(
        session,
        actor=identity.subject,
        action="session.disable",
        object_type="session",
        object_id=result["id"],
        after=result,
    )
    return result
