"""Public client bootstrap config (no secrets)."""

from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings

router = APIRouter()


@router.get("/config")
async def client_config() -> dict:
    settings = get_settings()
    return {
        "platform_tz": settings.platform_tz,
        "auth_mode": settings.auth_mode,
        "stub_login": settings.stub_login,
    }
