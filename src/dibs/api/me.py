"""The caller's own view: identity + standing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..auth.dependencies import current_identity
from ..auth.identity import Identity

router = APIRouter()


@router.get("")
async def get_me(request: Request, identity: Identity = Depends(current_identity)) -> dict:
    return {
        **identity.to_dict(),
        "is_admin": identity.is_admin,
        "is_sysadmin": identity.is_sysadmin,
        "csrf_token": request.state.session["csrf"],
    }
