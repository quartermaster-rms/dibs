"""Prometheus metrics (exposed on a loopback-only /metrics)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUESTS = Counter("dibs_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("dibs_http_request_seconds", "HTTP request latency", ["method", "path"])
NODE_OFFLINE = Counter("dibs_node_offline_total", "Interlock nodes marked offline")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        with LATENCY.labels(request.method, path).time():
            response = await call_next(request)
        REQUESTS.labels(request.method, path, response.status_code).inc()
        return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
