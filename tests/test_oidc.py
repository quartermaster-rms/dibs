from __future__ import annotations

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import Response

from dibs.auth import oidc
from dibs.cache import get_redis
from dibs.config import Settings
from dibs.errors import Unauthenticated

ISSUER = "https://kc.test/realms/dibs"
CLIENT_ID = "dibs"
DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": "https://kc.test/auth",
    "token_endpoint": "https://kc.test/token",
    "jwks_uri": "https://kc.test/jwks",
}


def _settings():
    return Settings(
        auth_mode="oidc",
        oidc_issuer=ISSUER,
        oidc_client_id=CLIENT_ID,
        oidc_client_secret="secret",
        oidc_redirect_url="https://app/api/auth/callback",
        cookie_secure=False,
    )


def _b64u(n: int) -> str:
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _jwk(pub, kid: str) -> dict:
    nums = pub.public_numbers()
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64u(nums.n),
        "e": _b64u(nums.e),
    }


def _sign(key, kid: str, claims: dict) -> str:
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def _claims(nonce: str, **over) -> dict:
    now = int(time.time())
    base = {
        "sub": "u-oidc",
        "name": "OIDC User",
        "email": "o@x",
        "groups": ["admin-dibs"],
        "nonce": nonce,
        "aud": CLIENT_ID,
        "iss": ISSUER,
        "exp": now + 300,
        "iat": now,
    }
    base.update(over)
    return base


KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = "test-key"


def test_generate_pkce():
    verifier, challenge = oidc.generate_pkce()
    assert verifier and challenge and "=" not in challenge


async def test_full_login_callback_flow(client, monkeypatch):
    settings = _settings()
    monkeypatch.setattr("dibs.auth.routes.get_settings", lambda: settings)
    with respx.mock:
        respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=Response(200, json=DISCOVERY)
        )
        respx.get("https://kc.test/jwks").mock(
            return_value=Response(200, json={"keys": [_jwk(KEY.public_key(), KID)]})
        )
        r = await client.get("/api/auth/login", follow_redirects=False)
        assert r.status_code == 307
        loc = r.headers["location"]
        assert loc.startswith("https://kc.test/auth?")
        state = parse_qs(urlparse(loc).query)["state"][0]
        flow = json.loads(await get_redis().get(f"oidc:{state}"))
        id_token = _sign(KEY, KID, _claims(flow["nonce"]))
        respx.post("https://kc.test/token").mock(
            return_value=Response(200, json={"id_token": id_token, "token_type": "Bearer"})
        )
        cb = await client.get(f"/api/auth/callback?code=abc&state={state}", follow_redirects=False)
        assert cb.status_code == 307 and cb.headers["location"] == "/"
    me = await client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["subject"] == "u-oidc" and me.json()["is_admin"] is True


async def test_login_and_callback_404_in_stub(client):
    # default profile is stub -> the OIDC endpoints are absent
    assert (await client.get("/api/auth/login", follow_redirects=False)).status_code == 404
    assert (
        await client.get("/api/auth/callback?code=a&state=b", follow_redirects=False)
    ).status_code == 404


async def test_callback_invalid_state(client, monkeypatch):
    monkeypatch.setattr("dibs.auth.routes.get_settings", lambda: _settings())
    r = await client.get("/api/auth/callback?code=a&state=missing", follow_redirects=False)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_state"


async def test_exchange_code_failure(clean_db):
    with respx.mock:
        respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=Response(200, json=DISCOVERY)
        )
        respx.post("https://kc.test/token").mock(return_value=Response(400, json={"error": "bad"}))
        with pytest.raises(Unauthenticated):
            await oidc.exchange_code(_settings(), "code", "verifier")


async def test_validate_id_token_paths(clean_db):
    settings = _settings()
    with respx.mock:
        respx.get(f"{ISSUER}/.well-known/openid-configuration").mock(
            return_value=Response(200, json=DISCOVERY)
        )
        respx.get("https://kc.test/jwks").mock(
            return_value=Response(200, json={"keys": [_jwk(KEY.public_key(), KID)]})
        )
        # nonce mismatch
        token = _sign(KEY, KID, _claims("expected"))
        with pytest.raises(Unauthenticated):
            await oidc.validate_id_token(settings, token, "different")
        # signing key not found (unknown kid)
        wrong_kid = _sign(KEY, "other-kid", _claims("n"))
        with pytest.raises(Unauthenticated):
            await oidc.validate_id_token(settings, wrong_kid, "n")
        # expired token
        expired = _sign(KEY, KID, _claims("n", exp=int(time.time()) - 10))
        with pytest.raises(Unauthenticated):
            await oidc.validate_id_token(settings, expired, "n")
        # happy path returns the identity
        good = _sign(KEY, KID, _claims("n"))
        identity = await oidc.validate_id_token(settings, good, "n")
        assert identity.subject == "u-oidc" and identity.is_admin
