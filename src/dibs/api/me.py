"""The caller's own view: identity, quota, notifications."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import current_identity, current_identity_csrf
from ..auth.identity import Identity
from ..db import get_session
from ..permissions.access import load_access
from ..permissions.deps import require_dibs_access
from ..services import audit, notifications, quotas

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
    access = await load_access(session, identity, equipment_id)
    return await quotas.quota_summary(session, identity, equipment_id, access.class_id)


@router.get("/notifications")
async def my_notifications(
    unread: bool = False,
    identity: Identity = Depends(current_identity),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await notifications.list_for(session, identity.subject, unread)


@router.post("/notifications/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    identity: Identity = Depends(current_identity_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await notifications.mark_read(session, identity.subject, notification_id)
    await audit.record(
        session,
        actor=identity.subject,
        action="notification.read",
        object_type="notification",
        object_id=notification_id,
    )
    return result
