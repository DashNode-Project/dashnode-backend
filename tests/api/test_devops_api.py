"""EP-16 DevOps practices hub API tests."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import DEFAULT_PASSWORD, create_user, login_as


def _create_project(client: TestClient, mgr_id: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "DevOps Hub",
            "description": "",
            "priority": "media",
            "tech_stack": [],
            "manager_id": mgr_id,
        },
    )
    assert response.status_code == 201, response.text
    project_id = response.json()["id"]
    assert isinstance(project_id, str)
    return project_id


def _sample_put() -> dict[str, Any]:
    return {
        "repository_url": "https://github.com/acme/dashnode",
        "ci_cd_provider": "GitHub Actions",
        "branching_strategy": "GitHub Flow",
        "branching_rules_md": "PR obligatorio a `main`.",
        "pipeline_stages": [
            {
                "order": 1,
                "name": "Lint",
                "tool": "Ruff + Mypy",
                "commands": "ruff check . && mypy .",
                "trigger_event": "Pull Request",
                "is_required": True,
            }
        ],
        "environments": [
            {
                "name": "Production",
                "url": "https://app.example.com",
                "branch": "main",
                "deploy_strategy": "Manual con aprobación",
                "requires_approval": True,
            }
        ],
        "quality_gates_md": "Cobertura >= 80%",
        "deployment_runbook_md": "Ejecutar migraciones Alembic.",
        "rollback_observability_md": "Revertir commit y redeploy.",
        "change_summary": "Configuración inicial",
    }


def test_openapi_has_devops_hub_paths(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/projects/{project_id}/devops" in paths
    assert "/api/v1/projects/{project_id}/devops/revisions" in paths
    assert "is_simulated" not in client.get("/openapi.json").text


def test_get_unconfigured_profile(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="devhub1@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    response = client.get(f"/api/v1/projects/{project_id}/devops")
    assert response.status_code == 200
    body = response.json()
    assert body["is_configured"] is False
    assert body["can_edit"] is True
    assert body["pipeline_stages"] == []


def test_manager_can_upsert_and_list_revisions(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="devhub2@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    put = client.put(f"/api/v1/projects/{project_id}/devops", json=_sample_put())
    assert put.status_code == 200
    body = put.json()
    assert body["is_configured"] is True
    assert len(body["pipeline_stages"]) == 1
    revisions = client.get(f"/api/v1/projects/{project_id}/devops/revisions")
    assert revisions.status_code == 200
    assert len(revisions.json()["items"]) == 1


def test_developer_can_read_but_not_put(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="devhub3mgr@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="devhub3dev@dashnode.io", role="developer")
    project_id = _create_project(client, mgr_id)
    assert (
        client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev_id}).status_code
        == 201
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "devhub3dev@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    read = client.get(f"/api/v1/projects/{project_id}/devops")
    assert read.status_code == 200
    assert read.json()["can_edit"] is False
    assert (
        client.put(f"/api/v1/projects/{project_id}/devops", json=_sample_put()).status_code == 403
    )


def test_non_member_forbidden(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="devhub4mgr@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    create_user(db_engine, email="outsider@dashnode.io", role="developer")
    client.post(
        "/api/v1/auth/login",
        json={"email": "outsider@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    assert client.get(f"/api/v1/projects/{project_id}/devops").status_code == 403


def test_not_found_project(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="devhub5@dashnode.io", role="manager")
    assert client.get("/api/v1/projects/missing/devops").status_code == 404


def test_unauthenticated(client: TestClient) -> None:
    assert client.get("/api/v1/projects/p-1/devops").status_code == 401


def test_validation_invalid_repo_url(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="devhub6@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    payload = _sample_put()
    payload["repository_url"] = "ftp://bad"
    response = client.put(f"/api/v1/projects/{project_id}/devops", json=payload)
    assert response.status_code == 400


def test_validation_duplicate_stage_order(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="devhub7@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    payload = _sample_put()
    stage = payload["pipeline_stages"][0]
    payload["pipeline_stages"] = [stage, {**stage, "name": "Test"}]
    response = client.put(f"/api/v1/projects/{project_id}/devops", json=payload)
    assert response.status_code == 400
