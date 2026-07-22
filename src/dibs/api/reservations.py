"""Reservation booking, modify, cancel, and listing."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..db import get_session
from ..permissions.deps import require_dibs_access, require_dibs_access_csrf
from ..services import audit, reservations
from ..services.idempotency import Idempotency

router = APIRouter()


class ReservationBody(BaseModel):
    starts_at: datetime
    ends_at: datetime


@router.get("/me/reservations")
async def my_reservations(
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await reservations.list_mine(session, identity)


@router.get("/equipment/{equipment_id}/reservations")
async def equipment_reservations(
    equipment_id: uuid.UUID,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await reservations.list_for_equipment(session, identity, equipment_id, from_, to)


@router.post("/equipment/{equipment_id}/reservations", status_code=201)
async def create_reservation(
    equipment_id: uuid.UUID,
    body: ReservationBody,
    request: Request,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    idem = Idempotency(session, identity.subject, request)
    replay = await idem.replay()
    if replay is not None:
        return replay
    res = await reservations.create_reservation(
        session, identity, equipment_id, body.starts_at, body.ends_at
    )
    await audit.record(
        session,
        actor=identity.subject,
        action="reservation.create",
        object_type="reservation",
        object_id=res["id"],
        after=res,
    )
    return await idem.store(201, res)


@router.patch("/reservations/{reservation_id}")
async def modify_reservation(
    reservation_id: uuid.UUID,
    body: ReservationBody,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await reservations.modify_reservation(
        session, identity, reservation_id, body.starts_at, body.ends_at
    )
    await audit.record(
        session,
        actor=identity.subject,
        action="reservation.modify",
        object_type="reservation",
        object_id=res["id"],
        after=res,
    )
    return res


@router.delete("/reservations/{reservation_id}")
async def cancel_reservation(
    reservation_id: uuid.UUID,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await reservations.cancel_reservation(session, identity, reservation_id)
    await audit.record(
        session,
        actor=identity.subject,
        action="reservation.cancel",
        object_type="reservation",
        object_id=res["id"],
        after=res,
    )
    return res
