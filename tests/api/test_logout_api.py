"""
HU_DN_01_04 - Cerrar sesion (HTTP contract).
Traceability: TK_DN_01_04_2 .. TK_DN_01_04_5.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.main import app
from app.orchestration import auth_container
from tests.fakes import FakeClock
from tests.support import DEFAULT_PASSWORD, create_user, login_as

URL = "/api/v1/auth/logout"
COOKIE = settings.SESSION_COOKIE_NAME


def test_logout_invalidates_session_clears_cookie_and_returns_literal_message(
    client: TestClient, db_engine: Engine
) -> None:
    login_as(client, db_engine, email="ana@empresa.com", role="manager")

    response = client.post(URL)

    assert response.status_code == 200
    assert response.json() == {"message": "Sesión cerrada correctamente."}
    cookie = response.headers["set-cookie"]
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie
    assert COOKIE not in client.cookies
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT revoked_at FROM sessions")).scalar_one() is not None


def test_previous_session_cookie_is_rejected_after_logout(
    client: TestClient, db_engine: Engine
) -> None:
    login_as(client, db_engine, email="ana@empresa.com", role="manager")
    old_token = client.cookies[COOKIE]
    client.post(URL)

    client.cookies.set(COOKIE, old_token)  # replay the stolen/previous cookie
    for path in ("/api/v1/auth/me", "/api/v1/projects", "/api/v1/notifications"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert client.post(URL).status_code == 200  # logging out again stays harmless


def test_logout_without_session_is_idempotent(client: TestClient) -> None:
    response = client.post(URL)
    assert response.status_code == 200
    assert response.json()["message"] == "Sesión cerrada correctamente."


def test_logout_of_expired_session_succeeds(
    client: TestClient, db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(auth_container, "clock", clock)
    login_as(client, db_engine, email="ana@empresa.com")
    clock.advance(hours=9)
    assert client.post(URL).status_code == 200


def test_logout_does_not_close_other_sessions_of_the_same_user(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email="ana@empresa.com")
    credentials = {"email": "ana@empresa.com", "password": DEFAULT_PASSWORD}
    client.post("/api/v1/auth/login", json=credentials)
    first_token = client.cookies[COOKIE]
    client.cookies.clear()
    client.post("/api/v1/auth/login", json=credentials)

    client.post(URL)  # closes the second session only
    client.cookies.set(COOKIE, first_token)
    assert client.get("/api/v1/auth/me").status_code == 200


def test_logout_from_a_foreign_origin_is_blocked_and_session_survives(
    client: TestClient, db_engine: Engine
) -> None:
    login_as(client, db_engine, email="ana@empresa.com")
    response = client.post(URL, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200


def test_technical_failure_returns_generic_message_and_keeps_the_cookie(
    db_engine: Engine,
) -> None:
    class Boom:
        def execute(self, _token: str | None) -> None:
            raise OperationalError("UPDATE sessions", {}, Exception("db down"))

    def broken() -> Generator[Boom, None, None]:
        yield Boom()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[auth_container.get_logout_use_case] = broken
    try:
        with TestClient(app, raise_server_exceptions=False) as failing_client:
            failing_client.cookies.set(COOKIE, "algun-token")
            response = failing_client.post(URL)
            assert COOKIE in failing_client.cookies  # nothing was cleared
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    assert response.status_code == 500
    assert response.json()["error"]["message"] == (
        "No fue posible completar la operación. Intente nuevamente."
    )
    assert "set-cookie" not in response.headers
