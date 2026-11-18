"""EP-16 DevOps pipeline API tests."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.modules.devops.infrastructure.models import DevopsPipelineStageRunModel
from tests.support import DEFAULT_PASSWORD, create_user, login_as


def _create_project(client: TestClient, mgr_id: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Pipeline Test",
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


def test_latest_pipeline_empty(client: TestClient, db_engine: Engine) -> None:
    mgr_id = create_user(db_engine, email="mgrpipe@dashnode.io", role="manager", name="Mgr Pipe")
    client.post(
        "/api/v1/auth/login",
        json={"email": "mgrpipe@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    project_id = _create_project(client, mgr_id)
    response = client.get(f"/api/v1/projects/{project_id}/devops/pipeline/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] is None
    assert body["stages"] == []
    assert body["is_simulated"] is True


def test_developer_cannot_trigger_pipeline(client: TestClient, db_engine: Engine) -> None:
    mgr_id = create_user(db_engine, email="mgrpipe2@dashnode.io", role="manager")
    create_user(db_engine, email="devpipe@dashnode.io", role="developer")
    client.post(
        "/api/v1/auth/login",
        json={"email": "mgrpipe2@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    project_id = _create_project(client, mgr_id)
    client.post(
        "/api/v1/auth/login",
        json={"email": "devpipe@dashnode.io", "password": DEFAULT_PASSWORD},
    )
    response = client.post(f"/api/v1/projects/{project_id}/devops/pipeline/runs")
    assert response.status_code == 403


def test_trigger_and_read_pipeline(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgrpipe3@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    created = client.post(f"/api/v1/projects/{project_id}/devops/pipeline/runs")
    assert created.status_code == 201
    latest = client.get(f"/api/v1/projects/{project_id}/devops/pipeline/latest")
    assert latest.status_code == 200
    body = latest.json()
    assert body["run_id"] == created.json()["run_id"]
    assert len(body["stages"]) == 4
    assert body["is_simulated"] is True


def test_pipeline_trigger_respects_cooldown(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgrpipe5@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    assert client.post(f"/api/v1/projects/{project_id}/devops/pipeline/runs").status_code == 201
    retry = client.post(f"/api/v1/projects/{project_id}/devops/pipeline/runs")
    assert retry.status_code == 429
    assert retry.json()["error"]["code"] == "COOLDOWN_ACTIVE"


def test_pipeline_not_found(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="mgrpipe6@dashnode.io", role="manager")
    response = client.get("/api/v1/projects/missing-project/devops/pipeline/latest")
    assert response.status_code == 404


def test_read_latest_does_not_write(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgrpipe4@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    client.post(f"/api/v1/projects/{project_id}/devops/pipeline/runs")
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = factory()
    try:
        before = session.query(DevopsPipelineStageRunModel).count()
        client.get(f"/api/v1/projects/{project_id}/devops/pipeline/latest")
        after = session.query(DevopsPipelineStageRunModel).count()
        assert before == after
    finally:
        session.close()
