from __future__ import annotations

import pytest
from sqlalchemy import select
from starlette.requests import Request

from dibs.auth import session as sess
from dibs.auth.dependencies import (
    current_identity,
    current_identity_csrf,
    require_admin,
    require_admin_csrf,
)
from dibs.auth.identity import Identity
from dibs.config import Settings
from dibs.errors import Forbidden, Unauthenticated
from dibs.models import Principal


# --- Identity helpers (unit) ---


def test_identity_roles():
    admin = Identity("s", "Sys", "s@x", ("sysadmin", "group-eng"))
    assert admin.is_sysadmin and admin.is_admin and not admin.is_app_admin
    app_admin = Identity("a", "Adm", "a@x", ("admin-dibs",))
    assert app_admin.is_app_admin and app_admin.is_admin and not app_admin.is_sysadmin
    user = Identity("u", "U", "u@x", ("group-eng", "group-hr"))
    assert not user.is_admin
    assert user.department_groups == ("group-eng", "group-hr")


def test_identity_roundtrip():
    ident = Identity("u", "U", "u@x", ("group-eng",))
    assert Identity.from_dict(ident.to_dict()) == ident


# --- Session store (integration with redis) ---


async def test_session_roundtrip(clean_db):
    ident = Identity("u", "U", "u@x", ())
    sid, csrf = await sess.create_session(ident)
    data = await sess.load_session(sid)
    assert data["identity"]["subject"] == "u"
    assert data["csrf"] == csrf
    await sess.delete_session(sid)
    assert await sess.load_session(sid) is None


# --- Stub login + /me ---


async def test_stub_login_and_me(client, login):
    me = await login(subject="u-1", groups=("group-eng",))
    assert me["subject"] == "u-1"
    assert me["is_admin"] is False
    resp = await client.get("/api/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject"] == "u-1"
    assert body["groups"] == ["group-eng"]
    assert "csrf_token" in body


async def test_admin_login(client, login):
    me = await login(subject="admin", groups=("admin-dibs",))
    assert me["is_admin"] is True


async def test_me_requires_auth(client):
    resp = await client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


async def test_me_invalid_session(client):
    client.cookies.set("dibs_session", "bogus-session-id")
    resp = await client.get("/api/me")
    assert resp.status_code == 401


async def test_principal_cached_on_login(client, login, db_session):
    await login(subject="u-9", display_name="Nine", email="n@x", groups=("admin-dibs",))
    row = (
        await db_session.execute(select(Principal).where(Principal.subject == "u-9"))
    ).scalar_one()
    assert row.display_name == "Nine"
    assert row.email == "n@x"
    assert row.is_admin is True
    # re-login updates the cached row
    await login(subject="u-9", display_name="Nine B", email="n2@x", groups=())
    await db_session.commit()
    row2 = (
        await db_session.execute(select(Principal).where(Principal.subject == "u-9"))
    ).scalar_one()
    await db_session.refresh(row2)
    assert row2.display_name == "Nine B"
    assert row2.is_admin is False


# --- Logout + CSRF ---


async def test_logout(client, login):
    await login()
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 204
    assert (await client.get("/api/me")).status_code == 401


async def test_logout_requires_csrf(client, login):
    await login()
    resp = await client.post("/api/auth/logout", headers={"X-CSRF-Token": ""})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"
    resp = await client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"})
    assert resp.status_code == 403


async def test_stub_login_disabled_in_oidc(client, monkeypatch):
    oidc = Settings(
        auth_mode="oidc",
        oidc_issuer="https://kc.example",
        oidc_client_id="dibs",
        oidc_client_secret="secret",
    )
    monkeypatch.setattr("dibs.auth.routes.get_settings", lambda: oidc)
    resp = await client.post("/api/auth/stub-login", json={"subject": "u"})
    assert resp.status_code == 404


# --- Role dependencies (unit) ---


async def test_require_admin_unit():
    admin = Identity("a", "", "", ("admin-dibs",))
    user = Identity("u", "", "", ())
    assert await require_admin(identity=admin) is admin
    assert await require_admin_csrf(identity=admin) is admin
    with pytest.raises(Forbidden):
        await require_admin(identity=user)
    with pytest.raises(Forbidden):
        await require_admin_csrf(identity=user)


def _request(cookies=None, headers=None, method="POST") -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw_headers.append(
            (b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode())
        )
    return Request(
        {"type": "http", "method": method, "headers": raw_headers, "path": "/", "query_string": b""}
    )


async def test_current_identity_no_cookie():
    with pytest.raises(Unauthenticated):
        await current_identity(_request())


async def test_current_identity_csrf_branches(clean_db):
    ident = Identity("u", "U", "u@x", ())
    sid, csrf = await sess.create_session(ident)
    # correct token
    req = _request(cookies={"dibs_session": sid}, headers={"x-csrf-token": csrf})
    assert (await current_identity(req)).subject == "u"
    assert await current_identity_csrf(req, identity=ident) is ident
    # missing token
    req2 = _request(cookies={"dibs_session": sid})
    await current_identity(req2)
    with pytest.raises(Forbidden):
        await current_identity_csrf(req2, identity=ident)
