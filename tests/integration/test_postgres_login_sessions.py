"""
PostgreSQL integration: login, sessions and brute-force protection on the real engine.
"""

import threading

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config import settings
from app.shared.infrastructure.database import Base
from tests.support import DEFAULT_PASSWORD, create_user

pytestmark = pytest.mark.integration

EMAIL = "ana@empresa.com"


def _login(client: TestClient, password: str = DEFAULT_PASSWORD) -> int:
    response = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": password})
    return int(response.status_code)


def test_migrated_schema_matches_orm_models(pg_engine: Engine) -> None:
    with pg_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_login_creates_utc_session_and_session_cookie_works(
    pg_client: TestClient, pg_clean: Engine
) -> None:
    create_user(pg_clean, email=EMAIL, role="manager")
    assert _login(pg_client) == 200
    assert pg_client.get("/api/v1/auth/me").status_code == 200
    with pg_clean.connect() as conn:
        row = conn.execute(text("SELECT created_at, expires_at FROM sessions")).one()
    assert (row.expires_at - row.created_at).total_seconds() == settings.SESSION_TTL_HOURS * 3600
    assert row.expires_at.utcoffset().total_seconds() == 0


def test_parallel_wrong_passwords_never_exceed_the_attempt_limit(
    pg_client: TestClient, pg_clean: Engine
) -> None:
    create_user(pg_clean, email=EMAIL)
    statuses: list[int] = []

    def attempt() -> None:
        statuses.append(_login(pg_client, "Equivocada123"))

    threads = [threading.Thread(target=attempt) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Concurrency may reject slightly early (never late): at most 5 attempts are processed.
    assert statuses.count(401) <= settings.LOGIN_MAX_FAILED_ATTEMPTS
    assert statuses.count(401) + statuses.count(429) == 12
    with pg_clean.connect() as conn:
        recorded = conn.execute(text("SELECT COUNT(*) FROM login_attempts")).scalar_one()
    assert recorded <= settings.LOGIN_MAX_FAILED_ATTEMPTS


def test_deleting_a_user_cascades_to_sessions(pg_client: TestClient, pg_clean: Engine) -> None:
    user_id = create_user(pg_clean, email=EMAIL)
    assert _login(pg_client) == 200
    with pg_clean.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        assert conn.execute(text("SELECT COUNT(*) FROM sessions")).scalar_one() == 0
    assert pg_client.get("/api/v1/auth/me").status_code == 401


def test_logout_persists_revocation_and_blocks_replay(
    pg_client: TestClient, pg_clean: Engine
) -> None:
    create_user(pg_clean, email=EMAIL)
    assert _login(pg_client) == 200
    token = pg_client.cookies[settings.SESSION_COOKIE_NAME]

    assert pg_client.post("/api/v1/auth/logout").status_code == 200
    with pg_clean.connect() as conn:
        revoked = conn.execute(text("SELECT revoked_at FROM sessions")).scalar_one()
    assert revoked is not None

    pg_client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    assert pg_client.get("/api/v1/auth/me").status_code == 401
