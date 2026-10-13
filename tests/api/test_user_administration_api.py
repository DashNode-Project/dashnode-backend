"""EP-02 user administration HTTP contract (HU_DN_01_11 .. HU_DN_01_16)."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.modules.auth.domain import messages
from app.modules.projects.infrastructure.models import ProjectModel
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator
from tests.support import create_user, login_as

CREATE_URL = "/api/v1/auth/admin/users"
LIST_URL = "/api/v1/auth/admin/users"
INVITE_URL = "/api/v1/auth/manager/users/invite"


def test_admin_create_user_success(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    response = client.post(
        CREATE_URL,
        json={"name": "Carlos Dev", "email": "carlos@empresa.com", "role": "developer"},
    )
    assert response.status_code == 201
    assert response.json()["message"] == messages.USER_CREATED


def test_create_user_with_admin_role_forbidden(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    response = client.post(
        CREATE_URL,
        json={"name": "Evil", "email": "evil@empresa.com", "role": "admin"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"] == (
        "Acceso denegado. No tiene permisos para realizar esta acción."
    )


def test_manager_invite_developer(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="mgr@empresa.com", role="manager")
    response = client.post(
        INVITE_URL,
        json={"name": "Nuevo Dev", "email": "invite@empresa.com"},
    )
    assert response.status_code == 201
    assert response.json()["message"] == messages.INVITE_DEVELOPER_SUCCESS


def test_manager_invite_cannot_assign_manager(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="mgr@empresa.com", role="manager")
    response = client.post(
        INVITE_URL,
        json={"name": "X", "email": "x@empresa.com", "role": "manager"},
    )
    assert response.status_code == 403


def test_list_users_excludes_password_hash(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    response = client.get(LIST_URL)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    encoded = json.dumps(body)
    assert "hashed_password" not in encoded
    assert "hashed_" not in encoded


def test_list_users_filter_combined(client: TestClient, db_engine: Engine) -> None:
    admin_id = login_as(client, db_engine, email="admin@empresa.com", role="admin")
    create_user(db_engine, email="ana@empresa.com", role="manager", name="Ana Gerente")
    create_user(db_engine, email="bob@empresa.com", role="developer", name="Bob Dev")
    response = client.get(LIST_URL, params={"name": "Ana", "role": "manager"})
    assert response.status_code == 200
    emails = [row["email"] for row in response.json()]
    assert emails == ["ana@empresa.com"]
    assert admin_id  # used


def test_update_user_success(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    target_id = create_user(db_engine, email="edit@empresa.com", role="developer", name="Before")
    response = client.patch(
        f"/api/v1/auth/admin/users/{target_id}",
        json={"name": "After", "email": "edit@empresa.com", "role": "manager"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == messages.USER_UPDATED
    assert response.json()["user"]["name"] == "After"


def test_update_manager_with_projects_blocked(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    mgr_id = create_user(db_engine, email="lead@empresa.com", role="manager", name="Lead")
    now = SystemClock().now()
    session = sessionmaker(bind=db_engine, expire_on_commit=False)()
    try:
        session.add(
            ProjectModel(
                id=UuidGenerator().generate(),
                name="Proyecto Alpha",
                description="",
                owner_id=mgr_id,
                manager_id=mgr_id,
                priority="media",
                tech_stack="[]",
                status="planificacion",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.patch(
        f"/api/v1/auth/admin/users/{mgr_id}",
        json={"name": "Lead", "email": "lead@empresa.com", "role": "developer"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == messages.MANAGER_ROLE_CHANGE_BLOCKED
