"""Authentication endpoints (mounted under /api/auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..errors import NotFound
from ..services.principals import upsert_principal
from .dependencies import current_identity_csrf
from .identity import Identity
from .session import (
    clear_session_cookies,
    create_session,
    delete_session,
    set_session_cookies,
)

router = APIRouter()


class StubLoginBody(BaseModel):
    subject: str = Field(min_length=1)
    display_name: str = ""
    email: str = ""
    groups: list[str] = Field(default_factory=list)


def _identity_payload(identity: Identity, csrf_token: str) -> dict[str, object]:
    return {
        **identity.to_dict(),
        "is_admin": identity.is_admin,
        "is_sysadmin": identity.is_sysadmin,
        "csrf_token": csrf_token,
    }


async def _establish(identity: Identity, session: AsyncSession) -> JSONResponse:
    await upsert_principal(session, identity)
    session_id, csrf_token = await create_session(identity)
    response = JSONResponse(_identity_payload(identity, csrf_token))
    set_session_cookies(response, session_id, csrf_token)
    return response


@router.post("/stub-login")
async def stub_login(
    body: StubLoginBody, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    """Hermetic dev/test login. Absent (404) unless the stub profile is active."""
    if not get_settings().stub_login:
        raise NotFound("not found")
    identity = Identity(
        subject=body.subject,
        display_name=body.display_name,
        email=body.email,
        groups=tuple(body.groups),
    )
    return await _establish(identity, session)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, _: Identity = Depends(current_identity_csrf)
) -> Response:
    await delete_session(request.state.session_id)
    response = Response(status_code=204)
    clear_session_cookies(response)
    return response
