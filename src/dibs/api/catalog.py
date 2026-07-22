"""Locations, classes, equipment: public reads and admin CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_admin_csrf
from ..auth.identity import Identity
from ..db import get_session
from ..errors import NotFound
from ..models import Equipment, EquipmentClass, Location
from ..permissions.deps import require_dibs_access
from ..services import audit, catalog
from ..services.settings import get_setting

router = APIRouter()


# --- Request bodies ---


class LocationBody(BaseModel):
    building: str = Field(min_length=1)
    room: str = Field(min_length=1)


class LocationPatch(BaseModel):
    building: str | None = None
    room: str | None = None


class ClassBody(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    department_groups: list[str] = Field(default_factory=list)
    open_use: bool | None = None
    requires_enable: bool | None = None


class ClassPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    department_groups: list[str] | None = None
    open_use: bool | None = None
    requires_enable: bool | None = None


class EquipmentBody(BaseModel):
    name: str = Field(min_length=1)
    class_id: uuid.UUID
    location_id: uuid.UUID
    photo_path: str | None = None
    open_use: bool | None = None
    requires_enable: bool | None = None


class EquipmentPatch(BaseModel):
    name: str | None = None
    class_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    photo_path: str | None = None
    open_use: bool | None = None
    requires_enable: bool | None = None


# --- Reads ---


@router.get("/locations")
async def list_locations(
    _: Identity = Depends(require_dibs_access), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = (
        await session.execute(select(Location).order_by(Location.building, Location.room))
    ).scalars()
    return [catalog.location_dict(loc) for loc in rows]


@router.get("/classes")
async def list_classes(
    _: Identity = Depends(require_dibs_access), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    rows = (await session.execute(select(EquipmentClass).order_by(EquipmentClass.name))).scalars()
    return [catalog.class_dict(cls) for cls in rows]


@router.get("/equipment")
async def list_equipment(
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
    q: str | None = None,
    class_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    authorized: bool = False,
    enabled_by_me: bool = False,
) -> list[dict]:
    return await catalog.list_equipment(
        session,
        identity,
        q=q,
        class_id=class_id,
        location_id=location_id,
        authorized=authorized,
        enabled_by_me=enabled_by_me,
    )


@router.get("/equipment/by-qr/{qr_token}")
async def equipment_by_qr(
    qr_token: str,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await catalog.get_by_qr(session, identity, qr_token)


@router.get("/equipment/{equipment_id}/history")
async def equipment_history(
    equipment_id: uuid.UUID,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await catalog.equipment_history(session, identity, equipment_id)


@router.get("/equipment/{equipment_id}")
async def get_equipment(
    equipment_id: uuid.UUID,
    identity: Identity = Depends(require_dibs_access),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await catalog.get_equipment(session, identity, equipment_id)


# --- Admin CRUD: locations ---


@router.post("/locations", status_code=201)
async def create_location(
    body: LocationBody,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    loc = await catalog.create_location(session, body.building, body.room)
    await audit.record(
        session,
        actor=admin.subject,
        action="location.create",
        object_type="location",
        object_id=loc.id,
        after=catalog.location_dict(loc),
    )
    return catalog.location_dict(loc)


@router.patch("/locations/{location_id}")
async def update_location(
    location_id: uuid.UUID,
    body: LocationPatch,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    loc = await session.get(Location, location_id)
    if loc is None:
        raise NotFound("location not found")
    before = catalog.location_dict(loc)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(loc, field, value)
    await session.flush()
    await audit.record(
        session,
        actor=admin.subject,
        action="location.update",
        object_type="location",
        object_id=loc.id,
        before=before,
        after=catalog.location_dict(loc),
    )
    return catalog.location_dict(loc)


@router.delete("/locations/{location_id}", status_code=204)
async def delete_location(
    location_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> Response:
    loc = await session.get(Location, location_id)
    if loc is None:
        raise NotFound("location not found")
    before = catalog.location_dict(loc)
    await catalog.delete_row(session, loc)
    await audit.record(
        session,
        actor=admin.subject,
        action="location.delete",
        object_type="location",
        object_id=location_id,
        before=before,
    )
    return Response(status_code=204)


# --- Admin CRUD: classes ---


async def _class_defaults(session: AsyncSession, body: ClassBody) -> dict:
    data = body.model_dump()
    if data["open_use"] is None:
        data["open_use"] = await get_setting(session, "default_open_use")
    if data["requires_enable"] is None:
        data["requires_enable"] = await get_setting(session, "default_requires_enable")
    return data


@router.post("/classes", status_code=201)
async def create_class(
    body: ClassBody,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cls = await catalog.create_class(session, **await _class_defaults(session, body))
    await audit.record(
        session,
        actor=admin.subject,
        action="class.create",
        object_type="equipment_class",
        object_id=cls.id,
        after=catalog.class_dict(cls),
    )
    return catalog.class_dict(cls)


@router.patch("/classes/{class_id}")
async def update_class(
    class_id: uuid.UUID,
    body: ClassPatch,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cls = await session.get(EquipmentClass, class_id)
    if cls is None:
        raise NotFound("class not found")
    before = catalog.class_dict(cls)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)
    await session.flush()
    await audit.record(
        session,
        actor=admin.subject,
        action="class.update",
        object_type="equipment_class",
        object_id=cls.id,
        before=before,
        after=catalog.class_dict(cls),
    )
    return catalog.class_dict(cls)


@router.delete("/classes/{class_id}", status_code=204)
async def delete_class(
    class_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> Response:
    cls = await session.get(EquipmentClass, class_id)
    if cls is None:
        raise NotFound("class not found")
    before = catalog.class_dict(cls)
    await catalog.delete_row(session, cls)
    await audit.record(
        session,
        actor=admin.subject,
        action="class.delete",
        object_type="equipment_class",
        object_id=class_id,
        before=before,
    )
    return Response(status_code=204)


# --- Admin CRUD: equipment ---


def _equipment_dict(eq: Equipment) -> dict:
    return {
        "id": str(eq.id),
        "name": eq.name,
        "class_id": str(eq.class_id),
        "location_id": str(eq.location_id),
        "photo_path": eq.photo_path,
        "open_use": eq.open_use,
        "requires_enable": eq.requires_enable,
        "qr_token": eq.qr_token,
    }


@router.post("/equipment", status_code=201)
async def create_equipment(
    body: EquipmentBody,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await session.get(EquipmentClass, body.class_id) is None:
        raise NotFound("class not found")
    if await session.get(Location, body.location_id) is None:
        raise NotFound("location not found")
    data = body.model_dump()
    if data["open_use"] is None:
        data["open_use"] = await get_setting(session, "default_open_use")
    if data["requires_enable"] is None:
        data["requires_enable"] = await get_setting(session, "default_requires_enable")
    eq = await catalog.create_equipment(session, **data)
    await audit.record(
        session,
        actor=admin.subject,
        action="equipment.create",
        object_type="equipment",
        object_id=eq.id,
        after=_equipment_dict(eq),
    )
    return _equipment_dict(eq)


@router.patch("/equipment/{equipment_id}")
async def update_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentPatch,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> dict:
    eq = await session.get(Equipment, equipment_id)
    if eq is None:
        raise NotFound("equipment not found")
    before = _equipment_dict(eq)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(eq, field, value)
    await session.flush()
    await audit.record(
        session,
        actor=admin.subject,
        action="equipment.update",
        object_type="equipment",
        object_id=eq.id,
        before=before,
        after=_equipment_dict(eq),
    )
    return _equipment_dict(eq)


@router.delete("/equipment/{equipment_id}", status_code=204)
async def delete_equipment(
    equipment_id: uuid.UUID,
    admin: Identity = Depends(require_admin_csrf),
    session: AsyncSession = Depends(get_session),
) -> Response:
    eq = await session.get(Equipment, equipment_id)
    if eq is None:
        raise NotFound("equipment not found")
    before = _equipment_dict(eq)
    await catalog.delete_row(session, eq)
    await audit.record(
        session,
        actor=admin.subject,
        action="equipment.delete",
        object_type="equipment",
        object_id=equipment_id,
        before=before,
    )
    return Response(status_code=204)
