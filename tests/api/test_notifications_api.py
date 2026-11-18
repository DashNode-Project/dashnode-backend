"""API tests for EP-14 Notifications routes."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.notifications.infrastructure.models import NotificationModel
from app.shared.infrastructure.id_generator import UuidGenerator
from tests.support import login_as

_id_gen = UuidGenerator()


def _insert_notification(
    session: Session,
    *,
    recipient_id: str,
    actor_id: str | None = None,
    unread: bool = True,
) -> str:
    now = datetime.now(UTC)
    nid = _id_gen.generate()
    session.add(
        NotificationModel(
            id=nid,
            recipient_id=recipient_id,
            actor_id=actor_id,
            type="TASK_ASSIGNED",
            event_key=f"TASK_ASSIGNED:{nid}:1",
            project_id=None,
            entity_type="task",
            entity_id=nid,
            title="Tarea asignada",
            message='Se le asignó la tarea "Demo" en DashNode.',
            created_at=now,
            read_at=None if unread else now,
            expires_at=now + timedelta(days=180),
        )
    )
    session.commit()
    return nid


def test_notifications_list_mark_and_unread_count(client: TestClient, db_engine: Engine) -> None:
    user_id = login_as(client, db_engine, email="notifuser2@dashnode.io")
    with Session(db_engine) as session:
        nid = _insert_notification(session, recipient_id=user_id)

    list_resp = client.get("/api/v1/notifications?limit=25&unread_only=false")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert "items" in body
    assert any(item["id"] == nid for item in body["items"])

    count_resp = client.get("/api/v1/notifications/unread-count")
    assert count_resp.status_code == 200
    assert count_resp.json()["count"] >= 1

    read_resp = client.post("/api/v1/notifications/read", json={"ids": [nid]})
    assert read_resp.status_code == 200
    assert read_resp.json()["unread_count"] >= 0

    count_after = client.get("/api/v1/notifications/unread-count")
    assert count_after.json()["count"] == read_resp.json()["unread_count"]