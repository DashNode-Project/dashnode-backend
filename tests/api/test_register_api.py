"""
HU_DN_01_02 - Registrar cuenta con rol Gerente (HTTP contract).
Traceability: TK_DN_01_02_3, TK_DN_01_02_4, TK_DN_01_02_5, TK_DN_01_02_6, TK_DN_01_02_7.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config import settings
from tests.support import create_user

URL = "/api/v1/auth/register"
PASSWORD = "Segura123"


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "Ana Gómez",
        "email": "ana@empresa.com",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }
    data.update(overrides)
    return data


def _error(response_json: dict[str, dict[str, object]]) -> tuple[str, str, dict[str, str]]:
    error = response_json["error"]
    return str(error["code"]), str(error["message"]), dict(error["fields"])  # type: ignore[call-overload]


def test_register_manager_success_returns_201_without_sensitive_data(
    client: TestClient, db_engine: Engine
) -> None:
    response = client.post(URL, json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert (
        body["message"]
        == "Su cuenta de Gerente ha sido registrada correctamente. Puede iniciar sesión."
    )
    assert body["user"]["email"] == "ana@empresa.com"
    assert body["user"]["name"] == "Ana Gómez"
    assert body["user"]["role"] == "manager"
    assert body["user"]["is_active"] is True
    assert PASSWORD not in response.text
    assert "hashed_password" not in response.text
    assert "set-cookie" not in response.headers  # registration does not open a session

    with db_engine.connect() as conn:
        stored = conn.execute(text("SELECT hashed_password, role FROM users")).one()
    assert stored.role == "manager"
    assert stored.hashed_password.startswith("$argon2id$")
    assert PASSWORD not in stored.hashed_password


def test_registered_account_can_be_looked_up_case_insensitively_as_duplicate(
    client: TestClient,
) -> None:
    assert client.post(URL, json=_payload()).status_code == 201
    response = client.post(URL, json=_payload(email="ANA@Empresa.com", name="Otra Persona"))
    assert response.status_code == 409
    code, message, fields = _error(response.json())
    assert code == "EMAIL_ALREADY_REGISTERED"
    assert message == "Ya existe una cuenta registrada con este correo electrónico."
    assert fields == {"email": message}


def test_duplicate_against_user_created_by_other_means(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email="ana@empresa.com", role="developer")
    assert client.post(URL, json=_payload()).status_code == 409


@pytest.mark.parametrize("role", ["admin", "developer", "ADMIN"])
def test_public_registration_rejects_privileged_roles(
    client: TestClient, db_engine: Engine, role: str
) -> None:
    response = client.post(URL, json=_payload(role=role))
    assert response.status_code == 403
    code, message, _ = _error(response.json())
    assert code == "ROLE_NOT_ALLOWED"
    assert message == "El registro público solo está disponible para el rol Gerente."
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0


def test_extra_fields_cannot_override_role_or_activation(
    client: TestClient, db_engine: Engine
) -> None:
    response = client.post(URL, json=_payload(is_active=False, id="forced-id", hashed_password="x"))
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "manager"
    assert response.json()["user"]["is_active"] is True
    assert response.json()["user"]["id"] != "forced-id"


@pytest.mark.parametrize(
    ("overrides", "code", "message"),
    [
        ({"name": ""}, "NAME_REQUIRED", "El nombre completo es obligatorio."),
        ({"name": "   "}, "NAME_REQUIRED", "El nombre completo es obligatorio."),
        (
            {"email": "no-es-correo"},
            "EMAIL_INVALID",
            "El correo electrónico ingresado no tiene un formato válido.",
        ),
        (
            {"password": "corta1", "confirm_password": "corta1"},
            "PASSWORD_WEAK",
            "La contraseña no cumple los requisitos mínimos de seguridad.",
        ),
        (
            {"password": "SoloLetrasAqui", "confirm_password": "SoloLetrasAqui"},
            "PASSWORD_WEAK",
            "La contraseña no cumple los requisitos mínimos de seguridad.",
        ),
        ({"confirm_password": "Distinta123"}, "PASSWORD_MISMATCH", "Las contraseñas no coinciden."),
        (
            {"name": "", "email": "", "password": "", "confirm_password": ""},
            "REQUIRED_FIELDS",
            "Todos los campos obligatorios deben ser diligenciados.",
        ),
    ],
)
def test_validation_failures_return_400_with_literal_messages(
    client: TestClient, db_engine: Engine, overrides: dict[str, object], code: str, message: str
) -> None:
    response = client.post(URL, json=_payload(**overrides))
    assert response.status_code == 400
    got_code, got_message, fields = _error(response.json())
    assert (got_code, got_message) == (code, message)
    assert fields
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 0


def test_missing_fields_are_treated_as_blank(client: TestClient) -> None:
    response = client.post(URL, json={})
    assert response.status_code == 400
    assert _error(response.json())[:2] == (
        "REQUIRED_FIELDS",
        "Todos los campos obligatorios deben ser diligenciados.",
    )


def test_wrong_types_use_generic_invalid_request_without_echo(client: TestClient) -> None:
    response = client.post(URL, json=_payload(password=["Segura123"]))
    assert response.status_code == 400
    assert _error(response.json())[0] == "INVALID_REQUEST"
    assert "Segura123" not in response.text


def test_malformed_json_is_rejected_cleanly(client: TestClient) -> None:
    response = client.post(URL, content=b"{not-json", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert _error(response.json())[0] == "INVALID_REQUEST"


def test_injection_payloads_are_stored_as_inert_text(client: TestClient, db_engine: Engine) -> None:
    hostile = "Robert'); DROP TABLE users;-- <script>alert(1)</script>"
    response = client.post(URL, json=_payload(name=hostile[:100], email="x@y.co"))
    assert response.status_code == 201
    assert response.json()["user"]["name"] == hostile[:100]
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1


def test_password_is_never_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        client.post(URL, json=_payload())
        client.post(URL, json=_payload(confirm_password="Distinta123"))
    assert PASSWORD not in caplog.text
    assert "Distinta123" not in caplog.text


def test_register_endpoint_is_documented_in_openapi(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/auth/register"]["post"]
    assert "201" in operation["responses"]
    assert settings.APP_ENV != "production"
