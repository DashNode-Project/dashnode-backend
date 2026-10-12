"""
API tests for Notifications routes.
@sad 4.1.4
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import legacy_auth_headers


def test_notifications_crud_flow(client: TestClient, db_engine: Engine) -> None:
    headers = legacy_auth_headers(client, db_engine, email="notifuser@dashnode.io")

    # Get user id from /me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    user_id = me_resp.json()["id"]

    # Send notification
    notif_payload = {
        "recipient_id": user_id,
        "type": "task_assigned",
        "title": "Welcome notification",
        "message": "Welcome to DashNode",
    }
    send_resp = client.post("/api/v1/notifications", json=notif_payload, headers=headers)
    assert send_resp.status_code == 201
    notif_id = send_resp.json()["id"]

    # List notifications
    list_resp = client.get("/api/v1/notifications", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert any(n["id"] == notif_id for n in items)

    # Mark as read
    read_resp = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True
