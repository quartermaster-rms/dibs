"""Append-only audit trail: every action is recorded (guide §5 shape). Never
updated or deleted; surfaced to admins on the Audit page."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from ..logging import request_id_var
from ..models import Audit


def snapshot(obj: Any, *fields: str) -> dict[str, Any]:
    """A JSON-safe dict of selected fields of an ORM row, for before/after."""
    return jsonable_encoder({f: getattr(obj, f) for f in fields})


async def record(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    object_type: str,
    object_id: uuid.UUID | str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    session.add(
        Audit(
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=str(object_id) if object_id is not None else None,
            before=jsonable_encoder(before) if before is not None else None,
            after=jsonable_encoder(after) if after is not None else None,
            request_id=request_id_var.get(),
        )
    )
