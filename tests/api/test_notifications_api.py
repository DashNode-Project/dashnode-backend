"""
API tests for Notifications routes.
@sad 4.1.4
"""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.shared.infrastructure.database import Base, get_db_session

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db: Session = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_session] = override_get_db
client = TestClient(app)


def test_notifications_crud_flow() -> None:
    # 1. Register and login
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "notifuser@dashnode.io",
            "password": "Password1234!",
            "name": "Notification User",
            "role": "developer",
        },
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "notifuser@dashnode.io", "password": "Password1234!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get user id from /me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    user_id = me_resp.json()["id"]

    # 3. Send notification
    notif_payload = {
        "recipient_id": user_id,
        "type": "task_assigned",
        "title": "Welcome notification",
        "message": "Welcome to DashNode",
    }
    send_resp = client.post("/api/v1/notifications", json=notif_payload, headers=headers)
    assert send_resp.status_code == 201
    notif_id = send_resp.json()["id"]

    # 4. List notifications
    list_resp = client.get("/api/v1/notifications", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert any(n["id"] == notif_id for n in items)

    # 5. Mark as read
    read_resp = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True
