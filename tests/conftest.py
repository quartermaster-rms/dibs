from __future__ import annotations

import asyncio
import contextlib
import os
import sys

if sys.platform == "win32":
    # psycopg async requires a selector loop; the default on Windows is Proactor.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("AUTH_MODE", "stub")
os.environ.setdefault("PLATFORM_TZ", "America/Los_Angeles")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://dibs:dibs@127.0.0.1:55432/dibs_test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:56379/0")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from dibs.app import create_app  # noqa: E402
from dibs.cache import get_redis  # noqa: E402
from dibs.db import get_sessionmaker  # noqa: E402
from dibs.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def clean_db():
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with get_sessionmaker()() as session:
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await session.commit()
    with contextlib.suppress(Exception):
        await get_redis().flushdb()
    yield


@pytest_asyncio.fixture
async def db_session():
    async with get_sessionmaker()() as session:
        yield session


@pytest_asyncio.fixture
async def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app, clean_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
