"""Fine-tier grant rosters and the delegation transition."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..db import get_session
from ..enums import ScopeKind, Tier
from ..permissions.delegation import GrantFlags
from ..permissions.deps import require_dibs_access, require_dibs_access_csrf
from ..services import audit, grants
from ..services.idempotency import Idempotency

router = APIRouter()


class GrantBody(BaseModel):
    subject: str
    scope_kind: ScopeKind
    scope_id: uuid.UUID
    tier: Tier
    can_promote: bool | None = None
    can_grant_superuser: bool | None = None
    can_demote: bool | None = None


@router.get("/equipment/{equipment_id}/grants")
async def item_grants(
    equipment_id: uuid.UUID,
    q: str | None = None,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await grants.list_item_grants(session, identity, equipment_id, q)


@router.get("/classes/{class_id}/grants")
async def class_grants(
    class_id: uuid.UUID,
    q: str | None = None,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await grants.list_class_grants(session, identity, class_id, q)


@router.put("/grants")
async def put_grant(
    body: GrantBody,
    request: Request,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    idem = Idempotency(session, identity.subject, request)
    replay = await idem.replay()
    if replay is not None:
        return replay
    provided = (body.can_promote, body.can_grant_superuser, body.can_demote)
    flags = (
        GrantFlags(bool(body.can_promote), bool(body.can_grant_superuser), bool(body.can_demote))
        if any(f is not None for f in provided)
        else None
    )
    before, after = await grants.put_grant(
        session, identity, body.subject, body.scope_kind, body.scope_id, body.tier, flags
    )
    await audit.record(
        session,
        actor=identity.subject,
        action="grant.set",
        object_type="role_grant",
        object_id=body.subject,
        before=before,
        after=after,
    )
    return await idem.store(200, after)
