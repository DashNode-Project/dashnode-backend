"""
PostgreSQL integration: migrations round trip and HU_DN_01_02 against the real engine.
"""

import threading

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, text

from tests.integration.conftest import alembic_config

pytestmark = pytest.mark.integration

PASSWORD = "Segura123"


def _payload(email: str = "ana@empresa.com") -> dict[str, str]:
    return {
        "name": "Ana Gómez",
        "email": email,
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }


def test_migrations_upgrade_downgrade_upgrade(temp_database_url: str) -> None:
    cfg = alembic_config(temp_database_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(temp_database_url)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()


def test_register_persists_manager_with_utc_timestamp(
    pg_client: TestClient, pg_clean: Engine
) -> None:
    response = pg_client.post("/api/v1/auth/register", json=_payload())
    assert response.status_code == 201
    with pg_clean.connect() as conn:
        row = conn.execute(text("SELECT role, hashed_password, created_at FROM users")).one()
    assert row.role == "manager"
    assert row.hashed_password.startswith("$argon2id$")
    assert row.created_at.utcoffset().total_seconds() == 0


def test_duplicate_email_conflict_on_real_unique_index(pg_client: TestClient) -> None:
    assert pg_client.post("/api/v1/auth/register", json=_payload()).status_code == 201
    second = pg_client.post("/api/v1/auth/register", json=_payload("ANA@empresa.com"))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_concurrent_registrations_create_exactly_one_account(
    pg_client: TestClient, pg_clean: Engine
) -> None:
    results: list[int] = []

    def register() -> None:
        results.append(
            pg_client.post("/api/v1/auth/register", json=_payload("race@empresa.com")).status_code
        )

    threads = [threading.Thread(target=register) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [201, 409, 409, 409]
    with pg_clean.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1


def test_readiness_probe_against_real_database(pg_client: TestClient) -> None:
    assert pg_client.get("/health/ready").json() == {"status": "ready"}
