"""
API tests for Projects routes.
@sad 4.1.2
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import create_user, login_as


def test_projects_crud_flow(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="pm@dashnode.io", role="manager")

    create_resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Alpha Project",
            "description": "First project",
            "priority": "media",
            "tech_stack": [],
            "manager_id": mgr_id,
        },
    )
    assert create_resp.status_code == 201
    proj_data = create_resp.json()
    assert proj_data["name"] == "Alpha Project"
    proj_id = proj_data["id"]

    list_resp = client.get("/api/v1/projects")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) >= 1
    assert any(p["id"] == proj_id for p in projects)

    get_resp = client.get(f"/api/v1/projects/{proj_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == proj_id

    dev_id = create_user(db_engine, email="dev-flow@dashnode.io", role="developer")
    add_resp = client.post(
        f"/api/v1/projects/{proj_id}/members",
        json={"user_id": dev_id},
    )
    assert add_resp.status_code == 201, add_resp.text
    assert add_resp.json()["message"] == "Miembro agregado correctamente."


def test_projects_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/projects").status_code == 401
