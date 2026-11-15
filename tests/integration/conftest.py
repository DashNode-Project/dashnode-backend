"""
PostgreSQL integration fixtures.

A throwaway database is created on the server given by TEST_POSTGRES_URL (a local
container or the CI service), migrated with Alembic exactly like production, and dropped
afterwards. Tests are skipped when no server is configured.
"""

import secrets
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.main import app
from app.shared.infrastructure.database import get_db_session

ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def _require_server() -> str:
    url = settings.TEST_POSTGRES_URL
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    assert url is not None
    return url


@pytest.fixture
def temp_database_url() -> Generator[str, None, None]:
    """Empty database (no schema) that is dropped after the test."""
    admin_url = _require_server()
    name = f"dashnode_it_{secrets.token_hex(4)}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope="module")
def pg_engine() -> Generator[Engine, None, None]:
    """Migrated database shared by the tests of a module."""
    admin_url = _require_server()
    name = f"dashnode_it_{secrets.token_hex(4)}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def pg_clean(pg_engine: Engine) -> Engine:
    """Empty every table before the test (keeps migrations)."""
    with pg_engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars()
        names = ", ".join(f'"{table}"' for table in tables)
        if names:
            conn.execute(text(f"TRUNCATE {names} CASCADE"))
    return pg_engine


@pytest.fixture
def pg_client(pg_clean: Engine) -> Generator[TestClient, None, None]:
    factory = sessionmaker(autocommit=False, autoflush=False, bind=pg_clean, expire_on_commit=False)

    def override() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db_session] = override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
