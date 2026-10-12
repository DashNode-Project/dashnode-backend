"""HU_DN_01_21 — profile HTTP contract."""

import io

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.auth.domain import messages
from tests.support import DEFAULT_PASSWORD, create_user, login_as

PROFILE = "/api/v1/auth/profile"


def test_get_and_update_profile(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="dev@empresa.com", role="developer")
    get_resp = client.get(PROFILE)
    assert get_resp.status_code == 200
    body = get_resp.json()["profile"]
    assert body["email"] == "dev@empresa.com"
    assert body["role"] == "developer"

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    patch_resp = client.patch(
        PROFILE,
        data={"name": "Nuevo Nombre"},
        files={"avatar": ("avatar.png", io.BytesIO(png), "image/png")},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["message"] == messages.PROFILE_UPDATED
    assert updated["profile"]["name"] == "Nuevo Nombre"
    assert updated["profile"]["avatar_url"]


def test_profile_name_required(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="mgr@empresa.com", role="manager")
    response = client.patch(PROFILE, data={"name": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["message"] == messages.NAME_REQUIRED


def test_inactive_user_cannot_login(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="off@empresa.com", role="developer", is_active=False)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "off@empresa.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"
