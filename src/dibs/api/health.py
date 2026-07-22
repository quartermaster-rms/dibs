"""Liveness/readiness with dependency checks (IMPLEMENTATION-GUIDE §2)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..cache import get_redis
from ..db import get_sessionmaker

router = APIRouter()


async def _check_db() -> bool:
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_cache() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


@router.get("/healthz")
async def healthz() -> JSONResponse:
    checks = {"db": await _check_db(), "cache": await _check_cache()}
    healthy = all(checks.values())
    body = {
        "status": "ok" if healthy else "unhealthy",
        "checks": {k: ("ok" if v else "fail") for k, v in checks.items()},
    }
    return JSONResponse(status_code=200 if healthy else 503, content=body)
