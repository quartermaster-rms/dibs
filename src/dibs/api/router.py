"""Assembles the user-plane API under /api."""

from __future__ import annotations

from fastapi import APIRouter

from ..auth.routes import router as auth_router
from .catalog import router as catalog_router
from .me import router as me_router
from .reservations import router as reservations_router


def build_api_router() -> APIRouter:
    api = APIRouter(prefix="/api")
    api.include_router(auth_router, prefix="/auth", tags=["auth"])
    api.include_router(me_router, prefix="/me", tags=["me"])
    api.include_router(catalog_router, tags=["catalog"])
    api.include_router(reservations_router, tags=["reservations"])
    return api
