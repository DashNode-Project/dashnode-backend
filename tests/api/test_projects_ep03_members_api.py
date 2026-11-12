"""API tests for EP-03 project members (HU_DN_02_27 .. HU_DN_02_28)."""

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from tests.support import create_user, login_as


def _create_project(client: TestClient, manager_id: str) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Team Project",
            "description": "",
            "priority": "media",
            "tech_stack": [],
            "meeting_link": None,
            "manager_id": manager_id,
        },
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]
    assert isinstance(project_id, str)
    return project_id


def test_hu_27_add_member(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr27@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev27@dashnode.io", role="developer")
    project_id = _create_project(client, mgr_id)

    add = client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev_id})
    assert add.status_code == 201, add.text
    assert add.json()["message"] == "Miembro agregado correctamente."

    members = client.get(f"/api/v1/projects/{project_id}/members")
    assert members.status_code == 200
    assert any(m["user_id"] == dev_id for m in members.json())


def test_hu_27_duplicate_member(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr27b@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev27b@dashnode.io", role="developer")
    project_id = _create_project(client, mgr_id)
    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev_id})
    dup = client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev_id})
    assert dup.status_code == 400
    assert dup.json()["error"]["fields"]["user_id"] == "El usuario ya es miembro de este proyecto."


def test_hu_27_developer_cannot_add(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr27c@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    other_dev = create_user(db_engine, email="dev27c-other@dashnode.io", role="developer")
    login_as(client, db_engine, email="dev27c@dashnode.io", role="developer")
    resp = client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": other_dev})
    assert resp.status_code == 403


def test_hu_28_remove_member(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr28@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev28@dashnode.io", role="developer")
    project_id = _create_project(client, mgr_id)
    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev_id})

    removed = client.delete(f"/api/v1/projects/{project_id}/members/{dev_id}")
    assert removed.status_code == 200
    assert removed.json()["message"] == "Miembro retirado correctamente."


def test_hu_28_cannot_remove_manager(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr28b@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    resp = client.delete(f"/api/v1/projects/{project_id}/members/{mgr_id}")
    assert resp.status_code == 400
    assert (
        resp.json()["error"]["fields"]["user_id"]
        == "No puede retirar al gerente responsable del proyecto."
    )


def test_hu_31_project_health(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr31@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    health = client.get(f"/api/v1/projects/{project_id}/health")
    assert health.status_code == 200
    body = health.json()
    assert body["progress_percent"] == 0.0
    assert body["velocity"] == 0.0
    assert body["open_issues"] == 0
