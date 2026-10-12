"""
Test bootstrap and shared fixtures.

Environment variables are set BEFORE the application package is imported so that the
settings object never reads a developer's real `.env` values. Argon2 cost is lowered
only here (tests), never in code defaults.
"""

import os

# Values below are non-secret test fixtures that only exist inside the test process.
_TEST_ENV = {
    "APP_ENV": "testing",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "ARGON2_TIME_COST": "1",
    "ARGON2_MEMORY_COST_KIB": "8",
    "ARGON2_PARALLELISM": "1",
    "CORS_ORIGINS": "http://localhost:5173,http://localhost:8080",
    "SESSION_COOKIE_SECURE": "false",
    "SEED_ADMIN_EMAIL": "",
    "SEED_ADMIN_PASSWORD": "",
    "SEED_DEVELOPER_EMAIL": "",
    "SEED_DEVELOPER_PASSWORD": "",
    "SEED_DISABLED_EMAIL": "",
    "SEED_DISABLED_PASSWORD": "",
}
for _key, _value in _TEST_ENV.items():
    os.environ[_key] = _value

# Imports below must stay after the environment bootstrap.
from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.main import app  # noqa: E402
from app.shared.infrastructure.database import Base, get_db_session  # noqa: E402


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    """Fresh in-memory SQLite database (full schema) per test."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    """API client wired to an isolated database; restores any previous override."""
    factory = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine, expire_on_commit=False
    )

    def override_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db_session] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
