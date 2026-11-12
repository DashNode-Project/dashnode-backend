"""HU_DN_01_06 / HU_DN_01_07 / HU_DN_01_10 — HTTP contract."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.auth.domain import messages
from tests.support import create_user, login_as

REQUEST_URL = "/api/v1/auth/password-reset/request"
PASSWORD = "Segura123"


def test_password_reset_request_agnostic(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="known@empresa.com", password=PASSWORD)
    for email in ("unknown@empresa.com", "known@empresa.com"):
        response = client.post(REQUEST_URL, json={"email": email})
        assert response.status_code == 200
        assert response.json()["message"] == messages.PASSWORD_RESET_REQUEST_SUCCESS


def test_password_reset_request_invalid_email(client: TestClient) -> None:
    response = client.post(REQUEST_URL, json={"email": "bad"})
    assert response.status_code == 400
    assert response.json()["error"]["message"] == messages.EMAIL_INVALID


def test_admin_users_forbidden_for_manager(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="mgr@empresa.com", role="manager")
    response = client.get("/api/v1/auth/admin/users")
    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "Acceso denegado. No tiene permisos para realizar esta acción."
    )
