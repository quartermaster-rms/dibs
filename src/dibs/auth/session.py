"""Server-side sessions (Redis) with an HTTP-only cookie and CSRF token.

The session cookie is HTTP-only + SameSite=Lax; CSRF is a double-submit token
required on every state-changing request (IMPLEMENTATION-GUIDE §3).
"""
from __future__ import annotations

import json
import secrets

from starlette.responses import Response

from ..cache import get_redis
from ..config import get_settings
from .identity import Identity

SESSION_COOKIE = "dibs_session"
CSRF_COOKIE = "dibs_csrf"
CSRF_HEADER = "x-csrf-token"

_SESSION_PREFIX = "session:"


def _key(session_id: str) -> str:
    return f"{_SESSION_PREFIX}{session_id}"


async def create_session(identity: Identity) -> tuple[str, str]:
    """Persist a new session; return (session_id, csrf_token)."""
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    payload = {"identity": identity.to_dict(), "csrf": csrf_token}
    await get_redis().set(
        _key(session_id), json.dumps(payload), ex=get_settings().session_ttl_seconds
    )
    return session_id, csrf_token


async def load_session(session_id: str) -> dict | None:
    raw = await get_redis().get(_key(session_id))
    if raw is None:
        return None
    return json.loads(raw)


async def delete_session(session_id: str) -> None:
    await get_redis().delete(_key(session_id))


def set_session_cookies(response: Response, session_id: str, csrf_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )
    # CSRF cookie is readable by the SPA so it can echo it in the header.
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(SESSION_COOKIE, domain=settings.cookie_domain, path="/")
    response.delete_cookie(CSRF_COOKIE, domain=settings.cookie_domain, path="/")
