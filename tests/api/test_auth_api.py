"""
API tests for the legacy Auth login/me routes (replaced by session auth in HU_DN_01_03).
@sad 4.1.1
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import DEFAULT_PASSWORD, create_user


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_and_me_flow(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="testuser@dashnode.io", name="Integration User")
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "testuser@dashnode.io"
    assert me_resp.json()["name"] == "Integration User"


def test_login_invalid_credentials(client: TestClient) -> None:
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@dashnode.io", "password": "WrongPassword123!"},
    )
    assert login_resp.status_code == 401
