"""
API tests for Tasks routes.
@sad 4.1.3
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import DEFAULT_PASSWORD, create_user, login_as


def switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 200, res.text


def test_tasks_crud_flow(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="lead-mgr@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev-tasks@dashnode.io", role="developer")

    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Tasks Test Project",
            "description": "Testing tasks",
            "priority": "media",
            "manager_id": mgr_id,
        },
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]
    member_resp = client.post(
        f"/api/v1/projects/{proj_id}/members",
        json={"user_id": dev_id},
    )
    assert member_resp.status_code == 201, member_resp.text

    # Create task
    task_payload = {
        "project_id": proj_id,
        "title": "Build Architecture Archetype",
        "description": "Create strict layered project",
        "priority": "urgent",
    }
    create_resp = client.post("/api/v1/tasks", json=task_payload)
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    assert task_data["title"] == "Build Architecture Archetype"
    assert task_data["status"] == "todo"
    task_id = task_data["id"]

    # Get task by id
    get_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id

    # List project tasks
    list_resp = client.get(f"/api/v1/tasks/project/{proj_id}")
    assert list_resp.status_code == 200
    tasks = list_resp.json()
    assert len(tasks) >= 1
    assert any(t["id"] == task_id for t in tasks)

    assign_resp = client.patch(
        f"/api/v1/tasks/{task_id}/assign",
        json={"assignee_id": dev_id},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assignee_id"] == dev_id

    switch_user(client, "dev-tasks@dashnode.io")
    status_resp = client.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "in-progress"})
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "in-progress"
