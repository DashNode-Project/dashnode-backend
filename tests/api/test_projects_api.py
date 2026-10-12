"""
API tests for Projects routes.
@sad 4.1.2
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import login_as


def test_projects_crud_flow(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="pm@dashnode.io", role="manager")

    # Create project
    create_resp = client.post(
        "/api/v1/projects", json={"name": "Alpha Project", "description": "First project"}
    )
    assert create_resp.status_code == 201
    proj_data = create_resp.json()
    assert proj_data["name"] == "Alpha Project"
    proj_id = proj_data["id"]

    # List projects
    list_resp = client.get("/api/v1/projects")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) >= 1
    assert any(p["id"] == proj_id for p in projects)

    # Get single project
    get_resp = client.get(f"/api/v1/projects/{proj_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == proj_id

    # Add a member
    add_resp = client.post(
        f"/api/v1/projects/{proj_id}/members", json={"user_id": "dev-user-id", "role": "member"}
    )
    assert add_resp.status_code == 201
    member_data = add_resp.json()
    assert member_data["project_id"] == proj_id
    assert member_data["user_id"] == "dev-user-id"


def test_projects_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/projects").status_code == 401
