"""API tests for Availability and Meetings endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.availability.domain import messages
from tests.support import DEFAULT_PASSWORD, login_as


def test_availability_mine_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/v1/availability/mine")
    assert response.status_code == 401


def test_availability_mine_save_and_retrieve_and_no_changes(
    client: TestClient, db_engine: Engine
) -> None:
    login_as(client, db_engine, email="dev@dashnode.local", role="developer")
    week = "2026-10-12"

    # Initial query -> empty slots
    res_get = client.get(f"/api/v1/availability/mine?week={week}")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["week_start_date"] == week
    assert data_get["is_inherited"] is False
    assert data_get["slots"]["monday"] == []

    # Save availability
    payload = {
        "week_start_date": week,
        "slots": {
            "monday": [{"start": "09:00", "end": "10:00"}, {"start": "10:00", "end": "11:00"}],
            "tuesday": [{"start": "14:00", "end": "16:00"}],
        },
    }
    res_save = client.post("/api/v1/availability/mine", json=payload)
    assert res_save.status_code == 200
    assert res_save.json()["message"] == messages.AVAILABILITY_SAVED

    # Re-fetch -> merged 09:00-11:00
    res_get2 = client.get(f"/api/v1/availability/mine?week={week}")
    assert res_get2.status_code == 200
    monday_slots = res_get2.json()["slots"]["monday"]
    assert len(monday_slots) == 1
    assert monday_slots[0]["start"] == "09:00"
    assert monday_slots[0]["end"] == "11:00"

    # Save exact same -> 400 NO_CHANGES_TO_SAVE
    res_save_dup = client.post("/api/v1/availability/mine", json=payload)
    assert res_save_dup.status_code == 400
    assert res_save_dup.json()["error"]["code"] == "NO_CHANGES_TO_SAVE"
    assert res_save_dup.json()["error"]["message"] == messages.NO_CHANGES_TO_SAVE

    # Query next week -> inherited
    res_next = client.get("/api/v1/availability/mine?week=2026-10-19")
    assert res_next.status_code == 200
    assert res_next.json()["is_inherited"] is True
    assert len(res_next.json()["slots"]["monday"]) == 1


def test_availability_team_permissions(client: TestClient, db_engine: Engine) -> None:
    # Developer -> 403
    login_as(client, db_engine, email="dev2@dashnode.local", role="developer")
    res_dev = client.get("/api/v1/availability/team?week=2026-10-12")
    assert res_dev.status_code == 403

    # Manager -> 200
    login_as(client, db_engine, email="mgr@dashnode.local", role="manager")
    res_mgr = client.get("/api/v1/availability/team?week=2026-10-12")
    assert res_mgr.status_code == 200
    assert "users" in res_mgr.json()

    login_as(client, db_engine, email="adm@dashnode.local", role="admin")
    res_adm = client.get("/api/v1/availability/team?week=2026-10-12")
    assert res_adm.status_code == 403
    assert res_adm.json()["error"]["code"] == "ACCESS_DENIED"


def test_search_meeting_slots_and_create_meeting(client: TestClient, db_engine: Engine) -> None:
    # Create manager and log in
    mgr_id = login_as(client, db_engine, email="mgr2@dashnode.local", role="manager")

    # Set availability for u1 as logged-in user u1
    client.cookies.clear()
    u1 = login_as(client, db_engine, email="u1@dashnode.local", role="developer")
    client.post(
        "/api/v1/availability/mine",
        json={
            "week_start_date": "2026-10-12",
            "slots": {"monday": [{"start": "09:00", "end": "12:00"}]},
        },
    )

    # Set availability for u2
    client.cookies.clear()
    u2 = login_as(client, db_engine, email="u2@dashnode.local", role="developer")
    client.post(
        "/api/v1/availability/mine",
        json={
            "week_start_date": "2026-10-12",
            "slots": {"monday": [{"start": "10:00", "end": "14:00"}]},
        },
    )

    # Login back as manager
    client.cookies.clear()
    res_mgr_log = client.post(
        "/api/v1/auth/login", json={"email": "mgr2@dashnode.local", "password": DEFAULT_PASSWORD}
    )
    assert res_mgr_log.status_code == 200

    # Create project managed by mgr2 with members u1 and u2
    res_proj = client.post(
        "/api/v1/projects",
        json={
            "name": "Proyecto Sync",
            "description": "Sync project",
            "priority": "media",
            "tech_stack": ["Python"],
            "meeting_link": "https://meet.google.com/abc-defg-hij",
            "manager_id": mgr_id,
        },
    )
    assert res_proj.status_code == 201
    proj_id = res_proj.json()["id"]
    client.post(f"/api/v1/projects/{proj_id}/members", json={"user_id": u1})
    client.post(f"/api/v1/projects/{proj_id}/members", json={"user_id": u2})

    # Search invalid interval
    res_inv = client.post(
        "/api/v1/availability/search-slots",
        json={
            "interval_start": "18:00",
            "interval_end": "09:00",
            "days": ["monday"],
            "participant_ids": [u1, u2],
            "duration_hours": 1,
            "week_start_date": "2026-10-12",
        },
    )
    assert res_inv.status_code == 400
    assert res_inv.json()["error"]["message"] == messages.INVALID_TIME_INTERVAL

    # Search valid slots
    res_search = client.post(
        "/api/v1/availability/search-slots",
        json={
            "interval_start": "08:00",
            "interval_end": "18:00",
            "days": ["monday"],
            "participant_ids": [u1, u2],
            "duration_hours": 1,
            "week_start_date": "2026-10-12",
        },
    )
    assert res_search.status_code == 200
    monday_data = next(d for d in res_search.json()["results"] if d["day"] == "monday")
    starts = [s["start"] for s in monday_data["slots"]]
    assert "10:00" in starts
    assert "11:00" in starts

    # Create meeting
    res_create = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Planning Scrum",
            "type": "Planning",
            "project_id": proj_id,
            "description": "Sprint sync",
            "date": "2026-10-12",
            "start_time": "10:00",
            "end_time": "11:00",
            "duration": 60,
            "participant_ids": [u1, u2],
        },
    )
    assert res_create.status_code == 201
    meeting_id = res_create.json()["id"]

    # Re-search -> 10:00 is now excluded because of the meeting!
    res_search2 = client.post(
        "/api/v1/availability/search-slots",
        json={
            "interval_start": "08:00",
            "interval_end": "18:00",
            "days": ["monday"],
            "participant_ids": [u1, u2],
            "duration_hours": 1,
            "week_start_date": "2026-10-12",
        },
    )
    assert res_search2.status_code == 200
    monday_data2 = next(d for d in res_search2.json()["results"] if d["day"] == "monday")
    starts2 = [s["start"] for s in monday_data2["slots"]]
    assert "10:00" not in starts2
    assert "11:00" in starts2

    # List meetings
    res_list = client.get("/api/v1/availability/meetings")
    assert res_list.status_code == 200
    assert any(m["id"] == meeting_id for m in res_list.json())
