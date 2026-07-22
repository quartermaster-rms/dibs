"""OIDC Authorization Code + PKCE against Keycloak, with ID-token validation via
the provider's JWKS (IMPLEMENTATION-GUIDE §3). The transient PKCE/nonce/state is
held server-side in Redis."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode

import httpx
import jwt

from ..cache import get_redis
from ..config import Settings
from ..errors import Unauthenticated
from .identity import Identity

_FLOW_TTL = 600


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


async def store_flow(state: str, verifier: str, nonce: str) -> None:
    await get_redis().set(
        f"oidc:{state}",
        json.dumps({"code_verifier": verifier, "nonce": nonce}),
        ex=_FLOW_TTL,
    )


async def load_flow(state: str) -> dict | None:
    raw = await get_redis().get(f"oidc:{state}")
    return json.loads(raw) if raw is not None else None


async def clear_flow(state: str) -> None:
    await get_redis().delete(f"oidc:{state}")


async def _discovery(settings: Settings) -> dict:
    issuer = settings.oidc_issuer.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{issuer}/.well-known/openid-configuration")
        resp.raise_for_status()
        return resp.json()


async def build_authorize_url(
    settings: Settings, state: str, code_challenge: str, nonce: str
) -> str:
    disc = await _discovery(settings)
    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": settings.oidc_redirect_url,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{disc['authorization_endpoint']}?{urlencode(params)}"


async def exchange_code(settings: Settings, code: str, code_verifier: str) -> dict:
    disc = await _discovery(settings)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            disc["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_url,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "code_verifier": code_verifier,
            },
        )
    if resp.status_code != 200:
        raise Unauthenticated("token exchange failed")
    return resp.json()


def _select_jwk(jwks: dict, kid: str) -> dict:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise Unauthenticated("signing key not found")


async def validate_id_token(settings: Settings, id_token: str, nonce: str) -> Identity:
    disc = await _discovery(settings)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(disc["jwks_uri"])
        resp.raise_for_status()
        jwks = resp.json()
    header = jwt.get_unverified_header(id_token)
    key = _select_jwk(jwks, header["kid"])
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    try:
        claims = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=disc["issuer"],
        )
    except jwt.PyJWTError as exc:
        raise Unauthenticated("invalid ID token") from exc
    if claims.get("nonce") != nonce:
        raise Unauthenticated("nonce mismatch")
    return Identity(
        subject=claims["sub"],
        display_name=claims.get("name", ""),
        email=claims.get("email", ""),
        groups=tuple(claims.get(settings.oidc_groups_claim, [])),
    )


def new_state() -> str:
    return secrets.token_urlsafe(32)
