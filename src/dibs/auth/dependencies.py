"""FastAPI auth dependencies. Fail-closed: any missing/invalid session -> 401,
insufficient role -> 403. CSRF is required on every state-changing request.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Request

from ..errors import Forbidden, Unauthenticated
from .identity import Identity
from .session import CSRF_HEADER, SESSION_COOKIE, load_session


async def current_identity(request: Request) -> Identity:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise Unauthenticated("authentication required")
    data = await load_session(session_id)
    if data is None:
        raise Unauthenticated("session expired")
    request.state.session = data
    request.state.session_id = session_id
    return Identity.from_dict(data["identity"])


async def current_identity_csrf(
    request: Request, identity: Identity = Depends(current_identity)
) -> Identity:
    token = request.headers.get(CSRF_HEADER)
    expected = request.state.session["csrf"]
    if not token or not secrets.compare_digest(token, expected):
        raise Forbidden("missing or invalid CSRF token", code="csrf_failed")
    return identity


async def require_admin(identity: Identity = Depends(current_identity)) -> Identity:
    if not identity.is_admin:
        raise Forbidden("administrator access required")
    return identity


async def require_admin_csrf(identity: Identity = Depends(current_identity_csrf)) -> Identity:
    if not identity.is_admin:
        raise Forbidden("administrator access required")
    return identity
