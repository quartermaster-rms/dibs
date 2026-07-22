"""Admin surface: Settings, quota-policy CRUD, analytics, and the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_admin, require_admin_csrf
from ..auth.identity import Identity
from ..db import get_session
from ..enums import QuotaType, QuotaWindow, ScopeKind
from ..errors import ValidationFailed
from ..services import audit, directory
from ..services import settings as settings_service

router = APIRouter()


class QuotaPolicyBody(BaseModel):
    quota_type: QuotaType
    principal: str
    target_kind: ScopeKind
    target_id: uuid.UUID
    window: QuotaWindow
    limit_hours: float
    hard_cap: bool = False
    active: bool = True


class QuotaPolicyPatch(BaseModel):
    principal: str | None = None
    limit_hours: float | None = None
    hard_cap: bool | None = None
    active: bool | None = None
    window: QuotaWindow | None = None


# --- Settings ---


@router.get("/settings")
async def get_settings_ep(
    _: Identity = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> dict:
    return await settings_service.get_all_settings(session)


@router.put("/settings")
async def put_settings(
    body: dict[str, Any],
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    unknown = set(body) - set(settings_service.DEFAULTS)
    if unknown:
        raise ValidationFailed(f"unknown settings: {sorted(unknown)}", code="unknown_setting")
    for key, value in body.items():
        await settings_service.set_setting(session, key, value)
    await audit.record(
        session, actor=admin.subject, action="settings.update", object_type="setting", after=body
    )
    return await settings_service.get_all_settings(session)


# --- Quota policies ---


@router.get("/quota-policies")
async def list_policies(
    _: Identity = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    return await settings_service.list_policies(session)


@router.post("/quota-policies", status_code=201)
async def create_policy(
    body: QuotaPolicyBody,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    policy = await settings_service.create_policy(session, **body.model_dump())
    result = settings_service.policy_dict(policy)
    await audit.record(
        session,
        actor=admin.subject,
        action="quota_policy.create",
        object_type="quota_policy",
        object_id=policy.id,
        after=result,
    )
    return result


@router.patch("/quota-policies/{policy_id}")
async def update_policy(
    policy_id: uuid.UUID,
    body: QuotaPolicyPatch,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    policy = await settings_service.update_policy(
        session, policy_id, body.model_dump(exclude_unset=True)
    )
    result = settings_service.policy_dict(policy)
    await audit.record(
        session,
        actor=admin.subject,
        action="quota_policy.update",
        object_type="quota_policy",
        object_id=policy_id,
        after=result,
    )
    return result


@router.delete("/quota-policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await settings_service.delete_policy(session, policy_id)
    await audit.record(
        session,
        actor=admin.subject,
        action="quota_policy.delete",
        object_type="quota_policy",
        object_id=policy_id,
    )
    return Response(status_code=204)


# --- Analytics ---


@router.get("/analytics/utilization")
async def analytics_utilization(
    class_id: uuid.UUID | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    _: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await directory.utilization(session, class_id, from_, to)


# --- Audit log ---


@router.get("/audit")
async def audit_log(
    actor: str | None = None,
    action: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    limit: int = 50,
    cursor: str | None = None,
    _: Identity = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await directory.list_audit(
        session,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        from_=from_,
        to=to,
        limit=min(max(limit, 1), 200),
        cursor=cursor,
    )
