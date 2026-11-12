"""
HU_DN_01_05 - Conservar la sesion al recargar la pagina (HTTP contract).
Traceability: TK_DN_01_05_1 .. TK_DN_01_05_5.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import settings
from app.main import app
from app.orchestration import auth_container
from tests.fakes import T0, FakeClock
from tests.support import DEFAULT_PASSWORD, create_user

URL = "/api/v1/auth/session"
COOKIE = settings.SESSION_COOKIE_NAME


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    clock = FakeClock()
    monkeypatch.setattr(auth_container, "clock", clock)
    return clock


def _login(client: TestClient, engine: Engine, *, role: str = "manager") -> dict[str, object]:
    create_user(engine, email="ana@empresa.com", role=role, name="Ana Gómez")
    response = client.post(
        "/api/v1/auth/login", json={"email": "ana@empresa.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def test_session_endpoint_returns_user_and_expiry(
    client: TestClient, db_engine: Engine, fake_clock: FakeClock
) -> None:
    login_body = _login(client, db_engine)

    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "ana@empresa.com"
    assert body["user"]["name"] == "Ana Gómez"
    assert body["user"]["role"] == "manager"
    assert body["expires_at"] == login_body["expires_at"]
    expires = datetime.fromisoformat(body["expires_at"])
    assert expires == T0 + timedelta(hours=8)
    assert expires.tzinfo is not None
    assert expires.astimezone(UTC) == expires


def test_page_reload_with_the_same_cookie_restores_the_session_without_renewing_it(
    client: TestClient, db_engine: Engine, fake_clock: FakeClock
) -> None:
    login_body = _login(client, db_engine)
    token = client.cookies[COOKIE]

    fake_clock.advance(hours=3)
    # A reload is a brand new browser context that only has the cookie.
    with TestClient(app) as reloaded:
        reloaded.cookies.set(COOKIE, token)
        response = reloaded.get(URL)

    assert response.status_code == 200
    assert response.json()["expires_at"] == login_body["expires_at"]  # not extended
    assert "set-cookie" not in response.headers  # no new cookie either


def test_expired_session_returns_literal_message_and_clears_cookie(
    client: TestClient, db_engine: Engine, fake_clock: FakeClock
) -> None:
    _login(client, db_engine)
    fake_clock.advance(hours=8)

    response = client.get(URL)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert response.json()["error"]["message"] == "Su sesión ha expirado. Inicie sesión nuevamente."
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert COOKIE not in client.cookies
    # afterwards the browser has no cookie and gets the plain "not authenticated" answer
    assert client.get(URL).json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_cookie_outlives_the_session_so_the_expiry_message_can_be_shown() -> None:
    assert settings.session_cookie_max_age_seconds > settings.session_ttl_seconds
    assert settings.session_ttl_seconds == 8 * 3600


def test_no_cookie_means_not_authenticated(client: TestClient) -> None:
    response = client.get(URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_session_of_a_user_disabled_after_login_is_refused(
    client: TestClient, db_engine: Engine
) -> None:
    _login(client, db_engine)
    from sqlalchemy import text

    with db_engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = 0"))
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "Su cuenta está desactivada. Contacte al Administrador."
    )


def test_response_never_exposes_credentials_or_token(client: TestClient, db_engine: Engine) -> None:
    _login(client, db_engine)
    response = client.get(URL)
    text = response.text.lower()
    assert "password" not in text
    assert "hash" not in text
    assert client.cookies[COOKIE] not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_session_endpoint_is_documented(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/auth/session"]["get"]
    assert {"200", "401", "403"} <= set(operation["responses"])


def test_session_endpoint_is_read_only(client: TestClient, db_engine: Engine) -> None:
    _login(client, db_engine)
    assert client.post(URL).status_code == 405
    assert client.delete(URL).status_code == 405
