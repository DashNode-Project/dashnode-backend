"""API tests for EP-13 AI metrics endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.ai_metrics.application.interaction_registry import (
    SOURCE_ASSISTANT_TEXT,
    InteractionRegistry,
)
from tests.support import login_as


def test_metrics_summary_forbidden_for_developer(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="dev-metrics@dashnode.local", role="developer")
    response = client.get("/api/v1/ai/metrics/summary")
    assert response.status_code == 403
    assert "Administrador y Gerente" in response.json()["error"]["message"]


def test_metrics_summary_admin(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    admin_id = login_as(client, db_engine, email="admin-metrics@dashnode.local", role="admin")
    registry = InteractionRegistry(db_session)
    iid = registry.start_pending(
        user_id=admin_id,
        project_id=None,
        source=SOURCE_ASSISTANT_TEXT,
        request_text="hola",
    )
    registry.complete_success(iid, response_text="respuesta", model_id="gemini")
    db_session.commit()

    response = client.get("/api/v1/ai/metrics/summary?period=today")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_interactions"] >= 1


def test_rating_own_interaction(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    dev_id = login_as(client, db_engine, email="dev-rate@dashnode.local", role="developer")
    registry = InteractionRegistry(db_session)
    iid = registry.start_pending(
        user_id=dev_id,
        project_id=None,
        source=SOURCE_ASSISTANT_TEXT,
        request_text="hola",
    )
    registry.complete_success(iid, response_text="ok", model_id=None)
    db_session.commit()

    response = client.put(
        f"/api/v1/ai/interactions/{iid}/rating",
        json={"score": 5, "comment": "útil"},
    )
    assert response.status_code == 200
    assert "registrada" in response.json()["message"].lower()