"""Issue reports: file/update/photo (any user), close (admin), and reads."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_admin_csrf
from ..auth.identity import Identity
from ..db import get_session
from ..enums import IssueStatus, Severity
from ..permissions.deps import require_dibs_access, require_dibs_access_csrf
from ..services import audit, issues
from ..services.idempotency import Idempotency

router = APIRouter()


class IssueBody(BaseModel):
    title: str = Field(min_length=1)
    severity: Severity
    description: str = ""


class UpdateBody(BaseModel):
    body: str = Field(min_length=1)


@router.post("/equipment/{equipment_id}/issues", status_code=201)
async def file_issue(
    equipment_id: uuid.UUID,
    body: IssueBody,
    request: Request,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    idem = Idempotency(session, identity.subject, request)
    replay = await idem.replay()
    if replay is not None:
        return replay
    issue = await issues.file_issue(
        session, identity, equipment_id, body.title, body.severity, body.description
    )
    await audit.record(
        session,
        actor=identity.subject,
        action="issue.file",
        object_type="issue",
        object_id=issue["id"],
        after=issue,
    )
    return await idem.store(201, issue)


@router.get("/equipment/{equipment_id}/issues")
async def equipment_issues(
    equipment_id: uuid.UUID,
    include_closed: bool = False,
    severity: Severity | None = None,
    q: str | None = None,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await issues.list_for_equipment(
        session, identity, equipment_id, include_closed, severity, q
    )


@router.get("/issues")
async def list_issues(
    status: IssueStatus | None = None,
    severity: Severity | None = None,
    equipment_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await issues.list_all(session, identity, status, severity, equipment_id, location_id)


@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: uuid.UUID,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await issues.get_issue(session, identity, issue_id)


@router.post("/issues/{issue_id}/updates", status_code=201)
async def add_update(
    issue_id: uuid.UUID,
    body: UpdateBody,
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    update = await issues.add_update(session, identity, issue_id, body.body)
    await audit.record(
        session,
        actor=identity.subject,
        action="issue.update",
        object_type="issue",
        object_id=str(issue_id),
        after=update,
    )
    return update


@router.post("/issues/{issue_id}/photos", status_code=201)
async def add_photo(
    issue_id: uuid.UUID,
    file: UploadFile = File(...),
    identity: Identity = Depends(require_dibs_access_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    photo = await issues.add_photo(session, identity, issue_id, file)
    await audit.record(
        session,
        actor=identity.subject,
        action="issue.photo",
        object_type="issue",
        object_id=str(issue_id),
        after={"path": photo["path"]},
    )
    return photo


@router.post("/issues/{issue_id}/close")
async def close_issue(
    issue_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    issue = await issues.close_issue(session, admin, issue_id)
    await audit.record(
        session,
        actor=admin.subject,
        action="issue.close",
        object_type="issue",
        object_id=issue["id"],
        after=issue,
    )
    return issue
