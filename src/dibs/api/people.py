"""The People directory (any authenticated dibs member)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..db import get_session
from ..permissions.deps import require_dibs_access
from ..services import directory

router = APIRouter()


@router.get("/people")
async def people(
    _: Identity = Depends(require_dibs_access), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    return await directory.list_people(session)
