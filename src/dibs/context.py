"""Request correlation: X-Request-Id handling (IMPLEMENTATION-GUIDE §2).

Accept a caller-supplied ``X-Request-Id`` only when it is a single well-formed
UUID; otherwise generate one. Echo it on the response. It is untrusted
correlation metadata and never influences auth, identity, or business logic.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging import request_id_var


def _valid_request_id(raw: str | None) -> str:
    if raw:
        try:
            return str(uuid.UUID(raw))
        except ValueError:
            pass
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        request_id = _valid_request_id(request.headers.get("x-request-id"))
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response
