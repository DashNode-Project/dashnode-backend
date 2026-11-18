"""PostgreSQL: DevOps pipeline migration and API (EP-16)."""

import pytest
from fastapi.testclient import TestClient

from tests.support import login_as

pytestmark = pytest.mark.integration


def _create_project(client: TestClient, mgr_id: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "DevOps PG",
            "description": "",
            "priority": "media",
            "manager_id": mgr_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_devops_pipeline_round_trip(pg_client: TestClient, pg_engine) -> None:
    mgr_id = login_as(pg_client, pg_engine, email="devopspg@dashnode.io", role="manager")
    project_id = _create_project(pg_client, mgr_id)
    empty = pg_client.get(f"/api/v1/projects/{project_id}/devops/pipeline/latest")
    assert empty.status_code == 200
    assert empty.json()["run_id"] is None
    created = pg_client.post(f"/api/v1/projects/{project_id}/devops/pipeline/runs")
    assert created.status_code == 201
    latest = pg_client.get(f"/api/v1/projects/{project_id}/devops/pipeline/latest")
    assert latest.status_code == 200
    body = latest.json()
    assert body["run_id"] is not None
    assert len(body["stages"]) == 4
