"""Device-plane FastAPI application (separate TLS port)."""

from __future__ import annotations

from fastapi import FastAPI

from ..config import Settings, get_settings
from ..context import RequestIdMiddleware
from ..errors import register_error_handlers
from ..logging import configure_logging
from .routes import router


def create_device_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(f"{settings.service_name}-device", settings.log_level)
    app = FastAPI(title="dibs-device", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(router)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    return app


app = create_device_app()
