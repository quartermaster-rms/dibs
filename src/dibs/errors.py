"""Error envelope and typed domain errors (IMPLEMENTATION-GUIDE §2).

Every non-2xx returns ``{"error": {"code","message","details"?}}``. HTTP status
conveys the class: 400 validation, 401 unauthenticated, 403 denied, 404 not
found, 409 conflict, 422 domain-rule, 429 rate-limited, 503 dependency down.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DibsError(Exception):
    status_code = 400
    code = "error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class ValidationFailed(DibsError):
    status_code = 400
    code = "validation_error"


class Unauthenticated(DibsError):
    status_code = 401
    code = "unauthenticated"


class Forbidden(DibsError):
    status_code = 403
    code = "forbidden"


class NotFound(DibsError):
    status_code = 404
    code = "not_found"


class Conflict(DibsError):
    status_code = 409
    code = "conflict"


class DomainRuleError(DibsError):
    status_code = 422
    code = "domain_error"


class RateLimited(DibsError):
    status_code = 429
    code = "rate_limited"


class DependencyUnavailable(DibsError):
    status_code = 503
    code = "dependency_unavailable"


def _envelope(code: str, message: str, details: dict[str, Any] | None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


def _json(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status, content=_envelope(code, message, details))


async def dibs_error_handler(_: Request, exc: DibsError) -> JSONResponse:
    return _json(exc.status_code, exc.code, exc.message, exc.details)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {
        400: "validation_error",
        401: "unauthenticated",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "domain_error",
        429: "rate_limited",
        503: "dependency_unavailable",
    }.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else code
    return _json(exc.status_code, code, message)


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _json(400, "validation_error", "request validation failed", {"errors": exc.errors()})


# Named domain errors with their fixed status codes (SPEC).
NAMED_ERRORS: dict[str, tuple[int, str]] = {
    "equipment_in_use": (409, "equipment is currently in use"),
    "fatal_fault_open": (422, "equipment has an open fatal issue"),
    "quota_exceeded": (422, "quota exceeded"),
    "grant_forbidden": (403, "grant transition not permitted"),
    "reservation_conflict": (409, "reservation overlaps an existing booking"),
    "reservation_immutable": (422, "reservation can no longer be changed"),
    "enable_not_supported": (422, "equipment is not enable-gated"),
    "slot_misaligned": (400, "times must align to the reservation slot granularity"),
    "advance_limit_exceeded": (422, "reservation is too far in advance"),
    "node_disabled": (409, "an interlock node is administratively disabled"),
    "starts_in_past": (422, "reservation must start in the future"),
    "department_gate": (403, "not a member of a required department group"),
    "not_active": (403, "account is not active"),
}


def named_error(
    code: str, message: str | None = None, details: dict[str, Any] | None = None
) -> DibsError:
    status, default = NAMED_ERRORS[code]
    return DibsError(message or default, code=code, status_code=status, details=details)


def register_error_handlers(app: Any) -> None:
    app.add_exception_handler(DibsError, dibs_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
