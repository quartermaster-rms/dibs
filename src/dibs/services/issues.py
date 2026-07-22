"""Issue reports: any user files/updates, only an admin closes. Equipment
status color is derived from open issues; on a transition into red or back into
green, upcoming reservation holders are notified. Filing/updating/closing never
touches a running session."""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..config import get_settings
from ..enums import IssueStatus, ReservationStatus, Severity, StatusColor
from ..errors import NotFound
from ..models import (
    Equipment,
    IssuePhoto,
    IssueReport,
    IssueUpdate,
    Principal,
    Reservation,
)
from ..permissions.access import load_access
from ..timeutil import now_utc, to_wire
from .notifications import notify


async def _color(session: AsyncSession, equipment_id: uuid.UUID) -> StatusColor:
    rows = await session.execute(
        select(IssueReport.severity, func.count())
        .where(IssueReport.equipment_id == equipment_id, IssueReport.status == IssueStatus.OPEN)
        .group_by(IssueReport.severity)
    )
    counts = dict(rows.all())
    if counts.get(Severity.FATAL, 0) > 0:
        return StatusColor.RED
    if counts.get(Severity.WARNING, 0) > 0:
        return StatusColor.YELLOW
    return StatusColor.GREEN


async def _notify_transition(
    session: AsyncSession, equipment_id: uuid.UUID, before: StatusColor, after: StatusColor
) -> None:
    if after == before:
        return
    if after == StatusColor.RED:
        message = "is out of service (a fatal issue was reported)"
    elif after == StatusColor.GREEN:
        message = "is back in service"
    else:
        return
    equipment = await session.get(Equipment, equipment_id)
    subjects = (
        await session.execute(
            select(Reservation.user_id)
            .where(
                Reservation.equipment_id == equipment_id,
                Reservation.status == ReservationStatus.BOOKED,
                Reservation.starts_at > now_utc(),
            )
            .distinct()
        )
    ).scalars()
    for subject in subjects:
        await notify(session, subject, f"{equipment.name} {message}.")


async def _names(session: AsyncSession, subjects: set[str]) -> dict[str, str]:
    if not subjects:
        return {}
    rows = await session.execute(
        select(Principal.subject, Principal.display_name).where(Principal.subject.in_(subjects))
    )
    return dict(rows.all())


def _summary(issue: IssueReport, last_update_at, name: str | None) -> dict:
    return {
        "id": str(issue.id),
        "equipment_id": str(issue.equipment_id),
        "title": issue.title,
        "severity": issue.severity.value,
        "status": issue.status.value,
        "reporter_id": issue.reporter_id,
        "reporter_name": name,
        "created_at": to_wire(issue.created_at),
        "last_update_at": to_wire(last_update_at) if last_update_at else to_wire(issue.created_at),
        "closed_by": issue.closed_by,
        "closed_at": to_wire(issue.closed_at),
    }


async def _last_updates(session: AsyncSession, issue_ids: list[uuid.UUID]) -> dict:
    if not issue_ids:
        return {}
    rows = await session.execute(
        select(IssueUpdate.issue_id, func.max(IssueUpdate.created_at))
        .where(IssueUpdate.issue_id.in_(issue_ids))
        .group_by(IssueUpdate.issue_id)
    )
    return dict(rows.all())


async def file_issue(
    session: AsyncSession,
    identity: Identity,
    equipment_id: uuid.UUID,
    title: str,
    severity: Severity,
    description: str,
) -> dict:
    await load_access(session, identity, equipment_id)  # reachability
    before = await _color(session, equipment_id)
    issue = IssueReport(
        equipment_id=equipment_id,
        reporter_id=identity.subject,
        title=title,
        severity=severity,
        description=description,
        status=IssueStatus.OPEN,
    )
    session.add(issue)
    await session.flush()
    after = await _color(session, equipment_id)
    await _notify_transition(session, equipment_id, before, after)
    return _summary(issue, None, None)


async def add_update(
    session: AsyncSession, identity: Identity, issue_id: uuid.UUID, body: str
) -> dict:
    issue = await session.get(IssueReport, issue_id)
    if issue is None:
        raise NotFound("issue not found")
    update = IssueUpdate(issue_id=issue_id, author_id=identity.subject, body=body)
    session.add(update)
    await session.flush()
    return {
        "id": str(update.id),
        "issue_id": str(issue_id),
        "author_id": identity.subject,
        "body": body,
        "created_at": to_wire(update.created_at),
    }


async def add_photo(
    session: AsyncSession,
    identity: Identity,
    issue_id: uuid.UUID,
    upload: UploadFile,
    update_id: uuid.UUID | None = None,
) -> dict:
    issue = await session.get(IssueReport, issue_id)
    if issue is None:
        raise NotFound("issue not found")
    suffix = Path(upload.filename or "").suffix
    stored = f"{uuid.uuid4().hex}{suffix}"
    content = await upload.read()
    uploads_dir = get_settings().uploads_dir

    def _persist() -> None:
        uploads = Path(uploads_dir)
        uploads.mkdir(parents=True, exist_ok=True)
        (uploads / stored).write_bytes(content)

    await anyio.to_thread.run_sync(_persist)
    photo = IssuePhoto(issue_id=issue_id, update_id=update_id, path=stored)
    session.add(photo)
    await session.flush()
    return {"id": str(photo.id), "issue_id": str(issue_id), "path": stored}


async def close_issue(session: AsyncSession, identity: Identity, issue_id: uuid.UUID) -> dict:
    issue = await session.get(IssueReport, issue_id)
    if issue is None:
        raise NotFound("issue not found")
    if issue.status == IssueStatus.CLOSED:
        return _summary(issue, None, None)
    before = await _color(session, issue.equipment_id)
    issue.status = IssueStatus.CLOSED
    issue.closed_by = identity.subject
    issue.closed_at = now_utc()
    await session.flush()
    after = await _color(session, issue.equipment_id)
    await _notify_transition(session, issue.equipment_id, before, after)
    return _summary(issue, None, None)


async def get_issue(session: AsyncSession, identity: Identity, issue_id: uuid.UUID) -> dict:
    issue = await session.get(IssueReport, issue_id)
    if issue is None:
        raise NotFound("issue not found")
    await load_access(session, identity, issue.equipment_id)  # reachability
    updates = (
        (
            await session.execute(
                select(IssueUpdate)
                .where(IssueUpdate.issue_id == issue_id)
                .order_by(IssueUpdate.created_at)
            )
        )
        .scalars()
        .all()
    )
    photos = (
        (await session.execute(select(IssuePhoto).where(IssuePhoto.issue_id == issue_id)))
        .scalars()
        .all()
    )
    names = await _names(session, {issue.reporter_id} | {u.author_id for u in updates})
    detail = _summary(
        issue, updates[-1].created_at if updates else None, names.get(issue.reporter_id)
    )
    detail["description"] = issue.description
    detail["updates"] = [
        {
            "id": str(u.id),
            "author_id": u.author_id,
            "author_name": names.get(u.author_id),
            "body": u.body,
            "created_at": to_wire(u.created_at),
        }
        for u in updates
    ]
    detail["photos"] = [
        {"id": str(p.id), "path": p.path, "update_id": str(p.update_id) if p.update_id else None}
        for p in photos
    ]
    return detail


async def list_for_equipment(
    session: AsyncSession,
    identity: Identity,
    equipment_id: uuid.UUID,
    include_closed: bool,
    severity: Severity | None,
    q: str | None,
) -> list[dict]:
    await load_access(session, identity, equipment_id)
    stmt = select(IssueReport).where(IssueReport.equipment_id == equipment_id)
    if not include_closed:
        stmt = stmt.where(IssueReport.status == IssueStatus.OPEN)
    if severity is not None:
        stmt = stmt.where(IssueReport.severity == severity)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(IssueReport.title.ilike(like), IssueReport.description.ilike(like)))
    stmt = stmt.order_by(IssueReport.created_at.desc())
    return await _serialize_list(session, (await session.execute(stmt)).scalars().all())


async def list_all(
    session: AsyncSession,
    identity: Identity,
    status: IssueStatus | None,
    severity: Severity | None,
    equipment_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
) -> list[dict]:
    from ..permissions.access import reachable_equipment_ids

    stmt = select(IssueReport).join(Equipment, IssueReport.equipment_id == Equipment.id)
    if status is not None:
        stmt = stmt.where(IssueReport.status == status)
    if severity is not None:
        stmt = stmt.where(IssueReport.severity == severity)
    if equipment_id is not None:
        stmt = stmt.where(IssueReport.equipment_id == equipment_id)
    if location_id is not None:
        stmt = stmt.where(Equipment.location_id == location_id)
    stmt = stmt.order_by(IssueReport.created_at.desc())
    issues = (await session.execute(stmt)).scalars().all()
    reachable = await reachable_equipment_ids(session, identity)
    if reachable is not None:
        issues = [i for i in issues if i.equipment_id in reachable]
    return await _serialize_list(session, issues)


async def _serialize_list(session: AsyncSession, issues: list[IssueReport]) -> list[dict]:
    last = await _last_updates(session, [i.id for i in issues])
    names = await _names(session, {i.reporter_id for i in issues})
    return [_summary(i, last.get(i.id), names.get(i.reporter_id)) for i in issues]
