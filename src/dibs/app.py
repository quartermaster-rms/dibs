"""User-plane FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .api.health import router as health_router
from .api.router import build_api_router
from .config import Settings, get_settings
from .context import RequestIdMiddleware
from .errors import NotFound, register_error_handlers
from .logging import configure_logging
from .metrics import MetricsMiddleware, metrics_response


def _mount_spa(app: FastAPI, settings: Settings) -> None:
    """Serve the React SPA at / with deep-link fallback to index.html. Unknown
    /api/* and /device/* paths stay JSON 404s; static files are traversal-safe."""
    static_root = Path(settings.static_dir).resolve()
    index = static_root / "index.html"
    if not index.is_file():
        return
    uploads = Path(settings.uploads_dir)
    if uploads.is_dir():
        app.mount("/uploads", StaticFiles(directory=uploads), name="uploads")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "device/", "uploads/")):
            raise NotFound("not found")
        candidate = (static_root / full_path).resolve()
        if full_path and candidate.is_file() and static_root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


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
    app.include_router(build_api_router())

    _loopback = {"127.0.0.1", "::1", "localhost", "testclient", None}

    async def metrics(request: Request) -> Response:
        host = request.client.host if request.client else None
        if host not in _loopback:
            return Response(status_code=403)
        return metrics_response()

    app.add_route("/metrics", metrics, methods=["GET"])

    _mount_spa(app, settings)  # last: the catch-all must not shadow API routes
    return app


app = create_app()
