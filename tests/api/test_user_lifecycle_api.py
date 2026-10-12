"""HU_DN_01_17 / HU_DN_01_18 / HU_DN_01_19 — lifecycle HTTP contract."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.modules.auth.domain import messages
from app.modules.auth.infrastructure.models import SessionModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.tasks.infrastructure.models import TaskModel
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator
from tests.support import DEFAULT_PASSWORD, create_user, login_as

DEACTIVATE = "/api/v1/auth/admin/users/{}/deactivate"
REACTIVATE = "/api/v1/auth/admin/users/{}/reactivate"
PENDING = "/api/v1/auth/admin/users/{}/pending-assignments"


def test_deactivate_user_revokes_session(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    target_id = create_user(db_engine, email="dev@empresa.com", role="developer")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@empresa.com", "password": DEFAULT_PASSWORD},
    )
    assert login_response.status_code == 200

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@empresa.com", "password": DEFAULT_PASSWORD},
    )
    assert admin_login.status_code == 200

    response = client.post(DEACTIVATE.format(target_id))
    assert response.status_code == 200
    assert response.json()["message"] == messages.USER_DEACTIVATED

    session = sessionmaker(bind=db_engine)()
    try:
        rows = session.query(SessionModel).filter(SessionModel.user_id == target_id).all()
        assert rows
        assert all(r.revoked_at is not None for r in rows)
    finally:
        session.close()


def test_admin_cannot_deactivate_self(client: TestClient, db_engine: Engine) -> None:
    admin_id = login_as(client, db_engine, email="admin@empresa.com", role="admin")
    response = client.post(DEACTIVATE.format(admin_id))
    assert response.status_code == 400
    assert response.json()["error"]["message"] == messages.SELF_DEACTIVATE_BLOCKED


def test_deactivate_manager_with_projects_blocked(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    mgr_id = create_user(db_engine, email="lead@empresa.com", role="manager")
    now = SystemClock().now()
    session = sessionmaker(bind=db_engine, expire_on_commit=False)()
    try:
        session.add(
            ProjectModel(
                id=UuidGenerator().generate(),
                name="Proyecto",
                description="",
                owner_id=mgr_id,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(DEACTIVATE.format(mgr_id))
    assert response.status_code == 400
    assert response.json()["error"]["message"] == messages.MANAGER_DEACTIVATE_BLOCKED


def test_reactivate_user(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    target_id = create_user(db_engine, email="off@empresa.com", role="developer", is_active=False)
    response = client.post(REACTIVATE.format(target_id))
    assert response.status_code == 200
    assert response.json()["message"] == messages.USER_REACTIVATED


def test_pending_assignments_count(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin@empresa.com", role="admin")
    dev_id = create_user(db_engine, email="dev@empresa.com", role="developer")
    now = SystemClock().now()
    session = sessionmaker(bind=db_engine, expire_on_commit=False)()
    try:
        session.add(
            TaskModel(
                id=UuidGenerator().generate(),
                project_id=UuidGenerator().generate(),
                title="Tarea activa",
                description="",
                status="in-progress",
                priority="medium",
                assignee_id=dev_id,
                creator_id=dev_id,
                has_open_fix=False,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(PENDING.format(dev_id))
    assert response.status_code == 200
    assert response.json()["pending_count"] == 1
