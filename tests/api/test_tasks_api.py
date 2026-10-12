"""
API tests for Tasks routes.
@sad 4.1.3
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import login_as


def test_tasks_crud_flow(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="lead@dashnode.io", role="admin")

    # Create project
    proj_resp = client.post(
        "/api/v1/projects", json={"name": "Tasks Test Project", "description": "Testing tasks"}
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

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

    # Update status to in-progress
    status_resp = client.patch(f"/api/v1/tasks/{task_id}/status", json={"status": "in-progress"})
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "in-progress"

    # Assign task
    assign_resp = client.patch(
        f"/api/v1/tasks/{task_id}/assign", json={"assignee_id": "dev-user-99"}
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assignee_id"] == "dev-user-99"
