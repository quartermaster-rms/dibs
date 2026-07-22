"""Idempotency-Key replay (guide §2): the first committed result for a
(caller, key) pair is stored and replayed on retries. Authorization is
re-evaluated on every attempt (it happens in the route's dependencies, before
any replay), so a stored result is never a standing permission."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from ..errors import Conflict, ValidationFailed
from ..models import IdempotencyRecord

IDEMPOTENCY_HEADER = "idempotency-key"


class Idempotency:
    def __init__(self, session: AsyncSession, caller: str, request: Request) -> None:
        self.session = session
        self.caller = caller
        self.method = request.method
        self.path = request.url.path
        self.key = request.headers.get(IDEMPOTENCY_HEADER)
        if self.key is not None:
            try:
                uuid.UUID(self.key)
            except ValueError as exc:
                raise ValidationFailed(
                    "Idempotency-Key must be a UUID", code="invalid_idempotency_key"
                ) from exc

    async def replay(self) -> JSONResponse | None:
        if self.key is None:
            return None
        row = (
            await self.session.execute(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.caller == self.caller,
                    IdempotencyRecord.key == self.key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return JSONResponse(row.response_body, status_code=row.status_code)

    async def store(self, status_code: int, body: Any) -> JSONResponse:
        payload = jsonable_encoder(body)
        if self.key is not None:
            self.session.add(
                IdempotencyRecord(
                    caller=self.caller,
                    key=self.key,
                    method=self.method,
                    path=self.path,
                    status_code=status_code,
                    response_body=payload,
                )
            )
            try:
                await self.session.flush()
            except IntegrityError as exc:
                raise Conflict(
                    "a request with this Idempotency-Key is already in progress",
                    code="idempotency_conflict",
                ) from exc
        return JSONResponse(payload, status_code=status_code)
