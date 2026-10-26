"""API tests for EP-07 sprints (HU_DN_05_63 .. HU_DN_05_67)."""

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.modules.sprints.domain import messages as sprint_messages
from tests.support import DEFAULT_PASSWORD, create_user, login_as


def _switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 200, res.text


def _create_project(client: TestClient, mgr_id: str) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Sprint Project",
            "description": "EP-07",
            "priority": "media",
            "manager_id": mgr_id,
        },
    )
    assert resp.status_code == 201
    return str(resp.json()["id"])


def _create_epic_and_story(client: TestClient, project_id: str) -> tuple[str, str]:
    epic = client.post(
        f"/api/v1/projects/{project_id}/epics",
        json={"name": "Epic Sprint", "description": "", "color": "#3B82F6"},
    )
    assert epic.status_code == 201
    epic_id = epic.json()["id"]
    story = client.post(
        f"/api/v1/epics/{epic_id}/user-stories",
        json={
            "title": "HU en sprint",
            "user_role": "Como dev",
            "reason": "probar",
            "moscow_priority": "must_have",
        },
    )
    assert story.status_code == 201
    return epic_id, story.json()["id"]


def _create_sprint(
    client: TestClient,
    project_id: str,
    *,
    name: str = "Sprint 1",
    start: date | None = None,
    end: date | None = None,
) -> str:
    start = start or datetime.now(UTC).date() + timedelta(days=1)
    end = end or start + timedelta(days=14)
    resp = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={
            "name": name,
            "goal": "Objetivo de prueba",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def test_hu_63_create_sprint_validation_and_success(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-spr63@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)

    empty = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={
            "name": "  ",
            "start_date": "2026-11-01",
            "end_date": "2026-11-14",
        },
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["fields"]["name"] == sprint_messages.SPRINT_NAME_REQUIRED

    bad_range = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={
            "name": "Sprint X",
            "start_date": "2026-11-14",
            "end_date": "2026-11-01",
        },
    )
    assert bad_range.status_code == 400
    assert bad_range.json()["error"]["fields"]["end_date"] == sprint_messages.SPRINT_END_AFTER_START

    create_user(db_engine, email="dev-spr63@dashnode.io", role="developer")
    _switch_user(client, "dev-spr63@dashnode.io")
    forbidden = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={
            "name": "Sprint Dev",
            "start_date": "2026-11-01",
            "end_date": "2026-11-14",
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["message"] == sprint_messages.SPRINT_ACCESS_DENIED

    _switch_user(client, "mgr-spr63@dashnode.io")
    sprint_id = _create_sprint(client, project_id)
    listed = client.get(f"/api/v1/projects/{project_id}/sprints")
    assert listed.status_code == 200
    assert any(s["id"] == sprint_id for s in listed.json()["items"])


def test_hu_64_assign_story_to_sprint(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-spr64@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    _, story_id = _create_epic_and_story(client, project_id)
    sprint_id = _create_sprint(client, project_id)

    client.patch(
        f"/api/v1/user-stories/{story_id}/story-points",
        json={"story_points": 8},
    )

    assign = client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_id}/sprint",
        json={"sprint_id": sprint_id},
    )
    assert assign.status_code == 200
    body = assign.json()
    assert body["message"] == sprint_messages.STORY_ASSIGNED
    assert body["sprint_total_points"] == 8

    missing = client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_id}/sprint",
        json={"sprint_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == sprint_messages.SPRINT_NOT_FOUND


def test_hu_65_66_start_sprint_rules(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-spr65@dashnode.io", role="manager")
    project_id = _create_project(client, mgr_id)
    sprint_id = _create_sprint(client, project_id, name="Sprint vacío")

    no_stories = client.post(f"/api/v1/projects/{project_id}/sprints/{sprint_id}/start")
    assert no_stories.status_code == 400
    assert no_stories.json()["error"]["message"] == sprint_messages.SPRINT_START_NO_STORIES

    _, story_id = _create_epic_and_story(client, project_id)
    client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_id}/sprint",
        json={"sprint_id": sprint_id},
    )

    started = client.post(f"/api/v1/projects/{project_id}/sprints/{sprint_id}/start")
    assert started.status_code == 200
    assert started.json()["message"] == sprint_messages.SPRINT_STARTED
    assert started.json()["status"] == "ACTIVE"

    sprint_b = _create_sprint(client, project_id, name="Sprint B")
    _, story_b = _create_epic_and_story(client, project_id)
    client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_b}/sprint",
        json={"sprint_id": sprint_b},
    )
    conflict = client.post(f"/api/v1/projects/{project_id}/sprints/{sprint_b}/start")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["message"] == sprint_messages.SPRINT_ALREADY_ACTIVE


def test_hu_67_current_sprint_metrics(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-spr67@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev-spr67@dashnode.io", role="developer")
    project_id = _create_project(client, mgr_id)
    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev_id})

    empty = client.get(f"/api/v1/projects/{project_id}/sprints/current")
    assert empty.status_code == 200
    assert empty.json()["sprint"] is None
    assert empty.json()["message"] == sprint_messages.NO_ACTIVE_SPRINT

    sprint_id = _create_sprint(client, project_id)
    _, story_id = _create_epic_and_story(client, project_id)
    pts = client.patch(f"/api/v1/user-stories/{story_id}/story-points", json={"story_points": 8})
    assert pts.status_code == 200
    client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_id}/sprint",
        json={"sprint_id": sprint_id},
    )
    client.post(f"/api/v1/projects/{project_id}/sprints/{sprint_id}/start")

    current = client.get(f"/api/v1/projects/{project_id}/sprints/current")
    assert current.status_code == 200
    sprint = current.json()["sprint"]
    assert sprint is not None
    assert sprint["name"] == "Sprint 1"
    assert sprint["total_points"] == 8
    assert sprint["completed_points"] == 0
    assert sprint["pending_points"] == 8

    _switch_user(client, "dev-spr67@dashnode.io")
    dev_view = client.get(f"/api/v1/projects/{project_id}/sprints/current")
    assert dev_view.status_code == 200
    assert dev_view.json()["sprint"]["total_points"] == 8
