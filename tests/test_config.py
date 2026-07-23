from __future__ import annotations

from sqlalchemy import make_url

from dibs.config import Settings


def test_database_url_derived_and_url_encoded():
    # With no DATABASE_URL the app derives it from the POSTGRES_* parts, encoding
    # the password so one with URL-special characters round-trips correctly.
    s = Settings(
        database_url="",
        postgres_user="dibs",
        postgres_password="p@ss:w/rd1",
        postgres_host="postgres",
        postgres_port=5432,
        postgres_db="dibs",
        auth_mode="stub",
    )
    url = make_url(s.database_url)
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "dibs"
    assert url.password == "p@ss:w/rd1"  # decodes back to the original, unbroken
    assert url.host == "postgres" and url.port == 5432 and url.database == "dibs"


def test_explicit_database_url_overrides_parts():
    s = Settings(
        database_url="postgresql+psycopg://u:pw@ext-host:5432/other",
        postgres_password="ignored",
        auth_mode="stub",
    )
    assert s.database_url == "postgresql+psycopg://u:pw@ext-host:5432/other"
