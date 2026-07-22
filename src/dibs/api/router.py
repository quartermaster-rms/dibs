"""Assembles the user-plane API under /api."""

from __future__ import annotations

from fastapi import APIRouter

from ..auth.routes import router as auth_router
from .admin import router as admin_router
from .catalog import router as catalog_router
from .grants import router as grants_router
from .issues import router as issues_router
from .me import router as me_router
from .people import router as people_router
from .reservations import router as reservations_router
from .sessions import router as sessions_router


def build_api_router() -> APIRouter:
    api = APIRouter(prefix="/api")
    api.include_router(auth_router, prefix="/auth", tags=["auth"])
    api.include_router(me_router, prefix="/me", tags=["me"])
    api.include_router(catalog_router, tags=["catalog"])
    api.include_router(reservations_router, tags=["reservations"])
    api.include_router(sessions_router, tags=["sessions"])
    api.include_router(issues_router, tags=["issues"])
    api.include_router(grants_router, tags=["grants"])
    api.include_router(people_router, tags=["people"])
    api.include_router(admin_router, tags=["admin"])
    return api
