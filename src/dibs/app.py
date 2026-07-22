"""User-plane FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response

from .api.health import router as health_router
from .config import Settings, get_settings
from .context import RequestIdMiddleware
from .errors import register_error_handlers
from .logging import configure_logging
from .metrics import MetricsMiddleware, metrics_response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.service_name, settings.log_level)

    app = FastAPI(title="dibs", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    # RequestId is added last so it is the outermost middleware.
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)

    app.include_router(health_router)

    async def metrics(_: object) -> Response:
        return metrics_response()

    app.add_route("/metrics", metrics, methods=["GET"])
    return app


app = create_app()
