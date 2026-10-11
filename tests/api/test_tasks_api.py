"""
API tests for Tasks routes.
@sad 4.1.3, RN-TAR-01, AD-10
"""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.shared.infrastructure.database import Base, get_db_session

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db: Session = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_session] = override_get_db
client = TestClient(app)


def test_tasks_crud_flow() -> None:
    # 1. Register and login manager
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "lead@dashnode.io",
            "password": "Password1234!",
            "name": "Team Lead",
            "role": "admin",
        },
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "lead@dashnode.io", "password": "Password1234!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"name": "Tasks Test Project", "description": "Testing tasks"},
        headers=headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # 3. Create task
    task_payload = {
        "project_id": proj_id,
        "title": "Build Architecture Archetype",
        "description": "Create strict layered project",
        "priority": "urgent",
    }
    create_resp = client.post("/api/v1/tasks", json=task_payload, headers=headers)
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    assert task_data["title"] == "Build Architecture Archetype"
    assert task_data["status"] == "todo"
    task_id = task_data["id"]

    # 4. Get task by id
    get_resp = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id

    # 5. List project tasks
    list_resp = client.get(f"/api/v1/tasks/project/{proj_id}", headers=headers)
    assert list_resp.status_code == 200
    tasks = list_resp.json()
    assert len(tasks) >= 1
    assert any(t["id"] == task_id for t in tasks)

    # 6. Update status to in-progress
    status_resp = client.patch(
        f"/api/v1/tasks/{task_id}/status",
        json={"status": "in-progress"},
        headers=headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "in-progress"

    # 7. Assign task
    assign_resp = client.patch(
        f"/api/v1/tasks/{task_id}/assign",
        json={"assignee_id": "dev-user-99"},
        headers=headers,
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assignee_id"] == "dev-user-99"
