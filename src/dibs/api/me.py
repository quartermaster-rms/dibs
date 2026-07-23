"""The caller's own view: identity and quota."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import current_identity
from ..auth.identity import Identity
from ..db import get_session
from ..permissions.access import require_reachable
from ..permissions.deps import require_dibs_access
from ..services import quotas

router = APIRouter()


@router.get("")
async def get_me(request: Request, identity: Identity = Depends(current_identity)) -> dict:
    return {
        **identity.to_dict(),
        "is_admin": identity.is_admin,
        "is_sysadmin": identity.is_sysadmin,
        "csrf_token": request.state.session["csrf"],
    }


@router.get("/quota")
async def my_quota(
    equipment_id: uuid.UUID,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    access = await require_reachable(session, identity, equipment_id)
    return await quotas.quota_summary(session, identity, equipment_id, access.class_id)
