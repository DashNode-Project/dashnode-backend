"""
API tests for cross-cutting behaviour: error contract, security headers, CSRF origin
check and health probes.
@sad AD-07
"""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.main import app
from app.orchestration.error_handling import register_error_handlers
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.database import get_db_session


class _Body(BaseModel):
    email: str


@pytest.fixture
def error_client() -> Generator[TestClient, None, None]:
    """Mini app exposing one route per error path, wired to the real handlers."""
    mini = FastAPI()
    register_error_handlers(mini)

    @mini.get("/app-error/{kind}")
    def raise_app_error(kind: str) -> None:
        raise AppError("SAMPLE", "Mensaje literal.", ErrorKind(kind), {"campo": "detalle"})

    @mini.get("/expired")
    def raise_expired() -> None:
        raise AppError("SESSION_EXPIRED", "Su sesión ha expirado.", ErrorKind.UNAUTHENTICATED)

    @mini.post("/validated")
    def validated(body: _Body) -> None:
        return None

    @mini.get("/http")
    def raise_http() -> None:
        raise StarletteHTTPException(status_code=418, detail="Soy una tetera.")

    @mini.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal detail that must never leak: s3cr3t-token")

    with TestClient(mini, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("validation", 400),
        ("unauthenticated", 401),
        ("forbidden", 403),
        ("not_found", 404),
        ("conflict", 409),
        ("rate_limited", 429),
    ],
)
def test_app_error_maps_kind_to_status_and_contract(
    error_client: TestClient, kind: str, expected: int
) -> None:
    response = error_client.get(f"/app-error/{kind}")
    assert response.status_code == expected
    assert response.json() == {
        "error": {"code": "SAMPLE", "message": "Mensaje literal.", "fields": {"campo": "detalle"}}
    }


def test_session_expired_clears_cookie(error_client: TestClient) -> None:
    response = error_client.get("/expired")
    assert response.status_code == 401
    set_cookie = response.headers["set-cookie"]
    assert settings.SESSION_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "HttpOnly" in set_cookie


def test_validation_error_never_echoes_received_values(error_client: TestClient) -> None:
    response = error_client.post("/validated", json={"email": 123, "password": "Sup3rSecreta1"})
    body = response.json()
    assert response.status_code == 400
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert "email" in body["error"]["fields"]
    assert "Sup3rSecreta1" not in response.text


def test_http_exception_uses_contract(error_client: TestClient) -> None:
    response = error_client.get("/http")
    assert response.status_code == 418
    assert response.json()["error"] == {
        "code": "HTTP_418",
        "message": "Soy una tetera.",
        "fields": {},
    }


def test_unknown_route_uses_contract(error_client: TestClient) -> None:
    response = error_client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_404"


def test_unhandled_exception_returns_generic_message_without_leaking(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("ERROR", logger="dashnode.api"):
        response = error_client.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INTERNAL_ERROR",
        "message": "No fue posible completar la operación. Intente nuevamente.",
        "fields": {},
    }
    assert "s3cr3t-token" not in response.text
    assert "RuntimeError" in caplog.text


def test_security_headers_and_no_store_on_api(client: TestClient) -> None:
    health = client.get("/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert health.headers["referrer-policy"] == "no-referrer"
    assert "cache-control" not in health.headers

    api = client.get("/api/v1/projects")
    assert api.headers["cache-control"] == "no-store"


def test_origin_check_blocks_unknown_origin_on_unsafe_methods(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@b.co", "password": "Abcdef12"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_origin_check_allows_configured_origin_and_missing_origin(client: TestClient) -> None:
    allowed = settings.cors_origins_list[0]
    with_origin = client.post(
        "/api/v1/auth/login",
        json={"email": "a@b.co", "password": "Abcdef12"},
        headers={"Origin": allowed},
    )
    without_origin = client.post(
        "/api/v1/auth/login", json={"email": "a@b.co", "password": "Abcdef12"}
    )
    assert with_origin.status_code != 403
    assert without_origin.status_code != 403


def test_origin_check_does_not_apply_to_safe_methods(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200


def test_cors_preflight_allows_credentials_for_configured_origin(client: TestClient) -> None:
    allowed = settings.cors_origins_list[0]
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": allowed,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == allowed
    assert response.headers["access-control-allow-credentials"] == "true"


def test_liveness_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_readiness_reports_503_when_database_is_down() -> None:
    class BrokenSession:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("down"))

    def broken() -> Generator[BrokenSession, None, None]:
        yield BrokenSession()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db_session] = broken
    try:
        response = TestClient(app).get("/health/ready")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
