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


def test_notifications_mark_all_and_delete_all(client: TestClient, db_engine: Engine) -> None:
    user_id = login_as(client, db_engine, email="notifbulk@dashnode.io")
    with Session(db_engine) as session:
        _insert_notification(session, recipient_id=user_id)
        _insert_notification(session, recipient_id=user_id)

    all_read = client.post("/api/v1/notifications/read-all")
    assert all_read.status_code == 200
    assert all_read.json()["unread_count"] == 0

    deleted = client.post("/api/v1/notifications/delete-all", json={"confirm": True})
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 2

    empty_delete = client.post("/api/v1/notifications/delete-all", json={"confirm": True})
    assert empty_delete.json()["deleted"] == 0


def test_notifications_mark_read_validation(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="notifval@dashnode.io")
    empty = client.post("/api/v1/notifications/read", json={"ids": []})
    assert empty.status_code == 200
    assert empty.json()["updated"] == 0

    too_many = client.post(
        "/api/v1/notifications/read", json={"ids": [f"id-{i}" for i in range(101)]}
    )
    assert too_many.status_code == 400

    confirm = client.post("/api/v1/notifications/delete-all", json={"confirm": False})
    assert confirm.status_code == 400


def test_open_notification_not_found(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="notifopen@dashnode.io")
    res = client.post("/api/v1/notifications/missing-id/open")
    assert res.status_code == 404


def test_notifications_list_unread_and_pagination(client: TestClient, db_engine: Engine) -> None:
    user_id = login_as(client, db_engine, email="notifpage@dashnode.io")
    with Session(db_engine) as session:
        _insert_notification(session, recipient_id=user_id, actor_id=user_id)
        _insert_notification(session, recipient_id=user_id, actor_id=user_id, unread=False)

    unread_resp = client.get("/api/v1/notifications?unread_only=true&limit=1")
    assert unread_resp.status_code == 200
    body = unread_resp.json()
    assert len(body["items"]) == 1
    if body.get("next_cursor"):
        page2 = client.get(f"/api/v1/notifications?limit=1&cursor={body['next_cursor']}")
        assert page2.status_code == 200

    bad_cursor = client.get("/api/v1/notifications?cursor=not-valid")
    assert bad_cursor.status_code == 400
