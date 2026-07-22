from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile

if sys.platform == "win32":
    # psycopg async requires a selector loop; the default on Windows is Proactor.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "dibs-test-uploads"))
os.environ.setdefault("AUTH_MODE", "stub")
os.environ.setdefault("PLATFORM_TZ", "America/Los_Angeles")
os.environ.setdefault("COOKIE_SECURE", "false")  # test client speaks http
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
async def db_session(clean_db):
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


@pytest_asyncio.fixture
def login(client):
    """Stub-login the shared client as a subject; sets its CSRF header."""

    async def _login(
        subject: str = "u-1",
        display_name: str = "User One",
        email: str = "u1@example.edu",
        groups: tuple[str, ...] = (),
    ) -> dict:
        resp = await client.post(
            "/api/auth/stub-login",
            json={
                "subject": subject,
                "display_name": display_name,
                "email": email,
                "groups": list(groups),
            },
        )
        assert resp.status_code == 200, resp.text
        client.headers["X-CSRF-Token"] = resp.json()["csrf_token"]
        return resp.json()

    return _login
