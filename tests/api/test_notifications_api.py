"""
API tests for Notifications routes.
@sad 4.1.4
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import login_as


def test_notifications_crud_flow(client: TestClient, db_engine: Engine) -> None:
    user_id = login_as(client, db_engine, email="notifuser@dashnode.io")

    me_resp = client.get("/api/v1/auth/session")
    assert me_resp.json()["user"]["id"] == user_id

    # Send notification
    notif_payload = {
        "recipient_id": user_id,
        "type": "task_assigned",
        "title": "Welcome notification",
        "message": "Welcome to DashNode",
    }
    send_resp = client.post("/api/v1/notifications", json=notif_payload)
    assert send_resp.status_code == 201
    notif_id = send_resp.json()["id"]

    # List notifications
    list_resp = client.get("/api/v1/notifications")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert any(n["id"] == notif_id for n in items)

    # Mark as read
    read_resp = client.patch(f"/api/v1/notifications/{notif_id}/read")
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True
