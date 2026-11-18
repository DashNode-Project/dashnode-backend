"""EP-15 command catalog API tests."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import DEFAULT_PASSWORD, create_user, login_as


def _create_project(client: TestClient, mgr_id: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "CMD Project",
            "description": "",
            "priority": "media",
            "manager_id": mgr_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_openapi_exposes_commands_and_devops_paths(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/api/v1/commands" in paths
    assert "/api/v1/projects/{project_id}/devops/pipeline/latest" in paths


def test_admin_sees_user_administration_commands(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admincmd@dashnode.io", role="admin")
    labels = {item["label"] for item in client.get("/api/v1/commands").json()["commands"]}
    assert "Usuarios" in labels
    assert "Inicio" in labels


def test_commands_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/commands")
    assert response.status_code == 401


def test_catalog_exposes_assistant_action(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="asscmd@dashnode.io", role="developer")
    commands = client.get("/api/v1/commands").json()["commands"]
    assert any(item.get("action") == "OPEN_ASSISTANT" for item in commands)


def test_developer_cannot_see_admin_only_commands(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="devcmd@dashnode.io", role="developer")
    payload = client.get("/api/v1/commands").json()
    labels = {item["label"] for item in payload["commands"]}
    assert "Usuarios" not in labels
    assert "Nuevo proyecto" not in labels
    assert payload["catalog_version"] == "cmd-v1.0.0"
    assert client.get("/api/v1/commands").headers.get("cache-control") == "no-store"


def test_manager_sees_new_project_action(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="mgrcmd@dashnode.io", role="manager")
    labels = {item["label"] for item in client.get("/api/v1/commands").json()["commands"]}
    assert "Nuevo proyecto" in labels


def test_member_sees_project_scoped_commands(client: TestClient, db_engine: Engine) -> None:
    mgr_id = create_user(db_engine, email="mgrcmd2@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="devcmd2@dashnode.io", role="developer")
    client.post(
        "/api/v1/auth/login",
        json={"email": "mgrcmd2@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    project_id = _create_project(client, mgr_id)
    invite = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": dev_id},
    )
    assert invite.status_code in (201, 200), invite.text
    client.cookies.clear()
    client.post(
        "/api/v1/auth/login",
        json={"email": "devcmd2@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    routes = {
        item["route"]
        for item in client.get("/api/v1/commands").json()["commands"]
        if item.get("route")
    }
    assert f"/proyectos/{project_id}/devops" in routes
