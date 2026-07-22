"""Dependencies enforcing the dibs-wide department gate on the user plane."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import current_identity, current_identity_csrf
from ..auth.identity import Identity
from ..db import get_session
from ..errors import named_error
from ..services.settings import get_setting
from .tiers import department_gate_ok


async def _check_gate(identity: Identity, session: AsyncSession) -> None:
    gate = set(await get_setting(session, "dibs_department_groups"))
    if not department_gate_ok(identity.is_admin, set(identity.groups), gate):
        raise named_error("department_gate", "you are not permitted to access dibs")


async def require_dibs_access(
    identity: Identity = Depends(current_identity),
    session: AsyncSession = Depends(get_session),
) -> Identity:
    await _check_gate(identity, session)
    return identity


async def require_dibs_access_csrf(
    identity: Identity = Depends(current_identity_csrf),
    session: AsyncSession = Depends(get_session),
) -> Identity:
    await _check_gate(identity, session)
    return identity
