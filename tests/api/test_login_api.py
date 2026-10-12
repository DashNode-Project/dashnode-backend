"""
HU_DN_01_03 - Iniciar sesion (HTTP contract, cookie and brute-force protection).
Traceability: TK_DN_01_03_3 .. TK_DN_01_03_8.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config import settings
from app.orchestration import auth_container
from tests.fakes import FakeClock
from tests.support import DEFAULT_PASSWORD, create_user

URL = "/api/v1/auth/login"
EMAIL = "ana@empresa.com"


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    clock = FakeClock()
    monkeypatch.setattr(auth_container, "clock", clock)
    return clock


def _login(client: TestClient, password: str = DEFAULT_PASSWORD, email: str = EMAIL):  # type: ignore[no-untyped-def]
    return client.post(URL, json={"email": email, "password": password})


def test_successful_login_sets_httponly_cookie_and_hides_token(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL, role="manager", name="Ana Gómez")

    response = _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == EMAIL
    assert body["user"]["role"] == "manager"  # the client routes to the role home from this
    assert body["user"]["name"] == "Ana Gómez"
    assert "expires_at" in body
    assert "hashed_password" not in response.text

    cookie = response.headers["set-cookie"]
    token = client.cookies[settings.SESSION_COOKIE_NAME]
    assert cookie.startswith(f"{settings.SESSION_COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert "SameSite=lax" in cookie
    assert f"Max-Age={settings.session_cookie_max_age_seconds}" in cookie
    assert token not in response.text  # the token only travels in the cookie
    assert len(token) >= 43  # 256 bits of entropy, url-safe encoded


def test_session_is_created_on_the_server_and_only_its_digest_is_stored(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    _login(client)
    token = client.cookies[settings.SESSION_COOKIE_NAME]

    with db_engine.connect() as conn:
        rows = conn.execute(text("SELECT token_hash, revoked_at FROM sessions")).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert rows[0].token_hash != token
    assert rows[0].revoked_at is None


def test_each_login_gets_a_different_token(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    _login(client)
    first = client.cookies[settings.SESSION_COOKIE_NAME]
    client.cookies.clear()
    _login(client)
    assert client.cookies[settings.SESSION_COOKIE_NAME] != first


def test_cookie_authenticates_protected_endpoints(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL, role="manager")
    _login(client)
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.get("/api/v1/projects").status_code == 200


def test_protected_endpoints_reject_requests_without_session(client: TestClient) -> None:
    for path in ("/api/v1/auth/session", "/api/v1/projects", "/api/v1/notifications"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_bearer_header_is_not_a_valid_credential(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    _login(client)
    token = client.cookies[settings.SESSION_COOKIE_NAME]
    client.cookies.clear()
    response = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_forged_cookie_is_rejected_and_cleared(client: TestClient) -> None:
    client.cookies.set(settings.SESSION_COOKIE_NAME, "forged-token-value")
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_invalid_email_format_is_rejected_with_literal_message(client: TestClient) -> None:
    response = _login(client, email="no-es-correo")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMAIL_INVALID"
    assert (
        response.json()["error"]["message"]
        == "El correo electrónico ingresado no tiene un formato válido."
    )
    assert "set-cookie" not in response.headers


def test_blank_fields_are_rejected(client: TestClient) -> None:
    response = client.post(URL, json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUIRED_FIELDS"


def test_wrong_password_and_unknown_email_return_identical_401(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    wrong_password = _login(client, password="Equivocada123")
    unknown_email = _login(client, email="nadie@empresa.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"]["message"] == (
        "Credenciales no válidas. Verifique su correo y contraseña."
    )
    assert "set-cookie" not in wrong_password.headers


def test_disabled_account_message_and_no_session(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL, is_active=False)
    response = _login(client)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"
    assert response.json()["error"]["message"] == (
        "Su cuenta está desactivada. Contacte al Administrador."
    )
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM sessions")).scalar_one() == 0


def test_account_lock_after_five_failures_returns_429_even_with_right_password(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    for _ in range(5):
        assert _login(client, password="Equivocada123").status_code == 401

    locked = _login(client, password="Equivocada123")
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "LOGIN_ATTEMPTS_EXCEEDED"
    assert locked.json()["error"]["message"] == (
        "Ha superado el número de intentos permitidos. Intente nuevamente más tarde."
    )
    assert _login(client).status_code == 429  # correct password is refused while locked
    assert settings.SESSION_COOKIE_NAME not in client.cookies


def test_lock_lifts_after_the_15_minute_window(
    client: TestClient, db_engine: Engine, fake_clock: FakeClock
) -> None:
    create_user(db_engine, email=EMAIL)
    for _ in range(5):
        _login(client, password="Equivocada123")
    assert _login(client).status_code == 429

    fake_clock.advance(minutes=14, seconds=59)
    assert _login(client).status_code == 429
    fake_clock.advance(minutes=1, seconds=1)
    assert _login(client).status_code == 200


def test_lock_is_per_account(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    create_user(db_engine, email="otra@empresa.com")
    for _ in range(6):
        _login(client, password="Equivocada123")
    assert _login(client, email="otra@empresa.com").status_code == 200


def test_session_expires_exactly_8_hours_after_login(
    client: TestClient, db_engine: Engine, fake_clock: FakeClock
) -> None:
    create_user(db_engine, email=EMAIL)
    _login(client)

    fake_clock.advance(hours=7, minutes=59, seconds=59)
    assert client.get("/api/v1/auth/session").status_code == 200
    fake_clock.advance(seconds=1)
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert response.json()["error"]["message"] == "Su sesión ha expirado. Inicie sesión nuevamente."
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_credentials_never_appear_in_logs(
    client: TestClient, db_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    create_user(db_engine, email=EMAIL)
    with caplog.at_level("DEBUG"):
        _login(client, password="Equivocada123")
        _login(client)
    assert "Equivocada123" not in caplog.text
    assert DEFAULT_PASSWORD not in caplog.text
    assert client.cookies[settings.SESSION_COOKIE_NAME] not in caplog.text
