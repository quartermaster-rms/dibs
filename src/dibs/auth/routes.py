"""Authentication endpoints (mounted under /api/auth)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..errors import NotFound, ValidationFailed
from ..services.principals import upsert_principal
from . import oidc
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


async def _apply_session(response: Response, identity: Identity, session: AsyncSession) -> str:
    await upsert_principal(session, identity)
    session_id, csrf_token = await create_session(identity)
    set_session_cookies(response, session_id, csrf_token)
    return csrf_token


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
    await upsert_principal(session, identity)
    session_id, csrf_token = await create_session(identity)
    response = JSONResponse(_identity_payload(identity, csrf_token))
    set_session_cookies(response, session_id, csrf_token)
    return response


@router.get("/login")
async def oidc_login() -> RedirectResponse:
    settings = get_settings()
    if settings.auth_mode != "oidc":
        raise NotFound("not found")
    verifier, challenge = oidc.generate_pkce()
    state = oidc.new_state()
    nonce = oidc.new_state()
    await oidc.store_flow(state, verifier, nonce)
    url = await oidc.build_authorize_url(settings, state, challenge, nonce)
    return RedirectResponse(url, status_code=307)


@router.get("/callback")
async def oidc_callback(
    code: str, state: str, session: AsyncSession = Depends(get_session)
) -> RedirectResponse:
    settings = get_settings()
    if settings.auth_mode != "oidc":
        raise NotFound("not found")
    flow = await oidc.load_flow(state)
    if flow is None:
        raise ValidationFailed("invalid or expired authorization state", code="invalid_state")
    await oidc.clear_flow(state)
    tokens = await oidc.exchange_code(settings, code, flow["code_verifier"])
    identity = await oidc.validate_id_token(settings, tokens["id_token"], flow["nonce"])
    response = RedirectResponse(settings.oidc_post_login_redirect, status_code=307)
    await _apply_session(response, identity, session)
    return response


@router.post("/logout", status_code=204)
async def logout(request: Request, _: Identity = Depends(current_identity_csrf)) -> Response:
    await delete_session(request.state.session_id)
    response = Response(status_code=204)
    clear_session_cookies(response)
    return response
