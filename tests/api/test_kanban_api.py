"""API tests for EP-08 Kanban Board (HU_DN_05_72 .. HU_DN_05_76)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.modules.backlog.domain import messages as backlog_messages
from app.modules.kanban.domain import messages as kanban_messages
from tests.support import DEFAULT_PASSWORD, create_user, login_as


def _switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 200, res.text


def _setup_project_with_members(client: TestClient, db_engine: Engine) -> tuple[str, str, str, str]:
    """Returns (project_id, mgr_id, dev1_id, dev2_id)."""
    mgr_id = login_as(client, db_engine, email="mgr-kanban@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1-kanban@dashnode.io", role="developer")
    dev2_id = create_user(db_engine, email="dev2-kanban@dashnode.io", role="developer")

    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Kanban Project",
            "description": "EP-08",
            "priority": "media",
            "manager_id": mgr_id,
        },
    )
    assert resp.status_code == 201
    project_id = str(resp.json()["id"])

    # Add developers as project members
    m1 = client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev1_id})
    assert m1.status_code == 201
    m2 = client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev2_id})
    assert m2.status_code == 201

    return project_id, mgr_id, dev1_id, dev2_id


def test_hu_72_kanban_no_active_sprint(client: TestClient, db_engine: Engine) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    res = client.get(f"/api/v1/projects/{project_id}/kanban")
    assert res.status_code == 200
    data = res.json()
    assert data["active_sprint"] is None
    assert data["message"] == kanban_messages.NO_ACTIVE_SPRINT
    assert len(data["columns"]) == 6
    for col in data["columns"]:
        assert col["cards"] == []


def test_hu_72_kanban_active_sprint_and_role_restriction(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _mgr_id, dev1_id, dev2_id = _setup_project_with_members(client, db_engine)

    # Create epic, story, tasks
    epic = client.post(
        f"/api/v1/projects/{project_id}/epics",
        json={"name": "Epic 1", "description": "Desc", "color": "#8B5CF6"},
    )
    epic_id = epic.json()["id"]

    story = client.post(
        f"/api/v1/epics/{epic_id}/user-stories",
        json={
            "title": "HU Kanban",
            "user_role": "Como dev",
            "reason": "probar tablero",
            "moscow_priority": "must_have",
        },
    )
    story_id = story.json()["id"]

    # Create 2 tasks: task 1 for dev1, task 2 for dev2
    t1 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Tarea Dev 1", "task_type": "frontend"},
    )
    assert t1.status_code == 201
    t1_id = t1.json()["id"]
    client.patch(f"/api/v1/story-tasks/{t1_id}/assignee", json={"assignee_id": dev1_id})
    client.patch(f"/api/v1/story-tasks/{t1_id}/estimated-hours", json={"estimated_hours": 4.0})

    t2 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Tarea Dev 2", "task_type": "backend"},
    )
    assert t2.status_code == 201
    t2_id = t2.json()["id"]
    client.patch(f"/api/v1/story-tasks/{t2_id}/assignee", json={"assignee_id": dev2_id})
    client.patch(f"/api/v1/story-tasks/{t2_id}/estimated-hours", json={"estimated_hours": 6.0})

    # Create sprint, assign story, start sprint
    start = datetime.now(UTC).date()
    end = start + timedelta(days=14)
    sprint_res = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={"name": "Sprint 1", "start_date": start.isoformat(), "end_date": end.isoformat()},
    )
    sprint_id = sprint_res.json()["id"]

    assign_res = client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_id}/sprint",
        json={"sprint_id": sprint_id},
    )
    assert assign_res.status_code == 200

    start_res = client.post(f"/api/v1/projects/{project_id}/sprints/{sprint_id}/start")
    assert start_res.status_code == 200

    # Manager view: sees both tasks
    mgr_board = client.get(f"/api/v1/projects/{project_id}/kanban")
    assert mgr_board.status_code == 200
    mgr_data = mgr_board.json()
    assert mgr_data["active_sprint"]["id"] == sprint_id
    todo_col = next(c for c in mgr_data["columns"] if c["id"] == "TODO")
    card_ids = [c["id"] for c in todo_col["cards"]]
    assert t1_id in card_ids
    assert t2_id in card_ids

    # Card fields check
    card1 = next(c for c in todo_col["cards"] if c["id"] == t1_id)
    assert card1["title"] == "Tarea Dev 1"
    assert card1["task_type"] == "frontend"
    assert card1["estimated_hours"] == 4.0
    assert card1["assignee_id"] == dev1_id

    # Developer view: only sees their own tasks
    _switch_user(client, "dev1-kanban@dashnode.io")
    dev_board = client.get(f"/api/v1/projects/{project_id}/kanban")
    assert dev_board.status_code == 200
    dev_data = dev_board.json()
    dev_todo = next(c for c in dev_data["columns"] if c["id"] == "TODO")
    dev_card_ids = [c["id"] for c in dev_todo["cards"]]
    assert t1_id in dev_card_ids
    assert t2_id not in dev_card_ids


def test_hu_73_move_card_permissions_and_restrictions(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _mgr_id, dev1_id, dev2_id = _setup_project_with_members(client, db_engine)

    epic = client.post(
        f"/api/v1/projects/{project_id}/epics",
        json={"name": "Epic 2", "description": "", "color": "#10B981"},
    )
    story = client.post(
        f"/api/v1/epics/{epic.json()['id']}/user-stories",
        json={
            "title": "HU Move",
            "user_role": "dev",
            "reason": "test",
            "moscow_priority": "must_have",
        },
    )
    story_id = story.json()["id"]

    t1 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Task 1", "task_type": "frontend"},
    )
    t1_id = t1.json()["id"]
    client.patch(f"/api/v1/story-tasks/{t1_id}/assignee", json={"assignee_id": dev1_id})

    t2 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Task 2", "task_type": "backend"},
    )
    t2_id = t2.json()["id"]
    client.patch(f"/api/v1/story-tasks/{t2_id}/assignee", json={"assignee_id": dev2_id})

    # Developer 1 moves their own task: valid transition TODO -> IN_PROGRESS
    _switch_user(client, "dev1-kanban@dashnode.io")
    ok_move = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert ok_move.status_code == 200
    assert ok_move.json()["message"] == backlog_messages.TASK_STATUS_UPDATED
    assert ok_move.json()["status"] == "IN_PROGRESS"

    # Developer 1 tries to move Developer 2's task -> 403 Forbidden
    forbidden_move = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t2_id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert forbidden_move.status_code == 403
    assert forbidden_move.json()["error"]["message"] == backlog_messages.TASK_STATUS_OWN_ONLY

    # Moving to CORRECTION directly is forbidden -> 400 Validation
    _switch_user(client, "mgr-kanban@dashnode.io")
    correction_move = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/status",
        json={"status": "CORRECTION"},
    )
    assert correction_move.status_code == 400
    assert correction_move.json()["error"]["message"] == backlog_messages.TASK_STATUS_CORRECTION


def test_hu_74_wip_limits(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project_with_members(client, db_engine)

    # Manager updates WIP limit
    res = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        json={"wip_limit": 3},
    )
    assert res.status_code == 200
    assert res.json()["message"] == kanban_messages.WIP_LIMIT_UPDATED
    assert res.json()["wip_limit"] == 3

    # Board reflects WIP limit
    board_res = client.get(f"/api/v1/projects/{project_id}/kanban")
    in_prog = next(c for c in board_res.json()["columns"] if c["id"] == "IN_PROGRESS")
    assert in_prog["wip_limit"] == 3

    # Reset WIP limit ("Sin límite")
    reset_res = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        json={"wip_limit": None},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["wip_limit"] is None

    # Invalid limit < 1 rejected
    bad_limit = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        json={"wip_limit": 0},
    )
    assert bad_limit.status_code == 422 or bad_limit.status_code == 400

    # Developer cannot set WIP limits
    _switch_user(client, "dev1-kanban@dashnode.io")
    dev_wip = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        json={"wip_limit": 5},
    )
    assert dev_wip.status_code == 403


def test_hu_76_task_blockage_and_dependencies(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, dev1_id, _ = _setup_project_with_members(client, db_engine)

    epic = client.post(
        f"/api/v1/projects/{project_id}/epics",
        json={"name": "Epic Block", "description": "", "color": "#EF4444"},
    )
    story = client.post(
        f"/api/v1/epics/{epic.json()['id']}/user-stories",
        json={
            "title": "HU Block",
            "user_role": "dev",
            "reason": "test",
            "moscow_priority": "must_have",
        },
    )
    story_id = story.json()["id"]

    t1 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Task Predecessor", "task_type": "backend", "assignee_id": dev1_id},
    )
    t1_id = t1.json()["id"]

    t2 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Task Dependent", "task_type": "frontend", "assignee_id": dev1_id},
    )
    t2_id = t2.json()["id"]

    # Block Task 2 manually with reason
    block_res = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t2_id}/block",
        json={"is_blocked": True, "blocked_reason": "Esperando diseño de Figma"},
    )
    assert block_res.status_code == 200
    assert block_res.json()["is_blocked"] is True
    assert block_res.json()["blocked_reason"] == "Esperando diseño de Figma"

    # Link Task 2 dependency on Task 1
    dep_res = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t2_id}/block",
        json={
            "is_blocked": False,
            "blocked_reason": None,
            "blocked_by_task_id": t1_id,
        },
    )
    assert dep_res.status_code == 200
    assert dep_res.json()["blocked_by_task_id"] == t1_id

    # Self-dependency rejected
    self_dep = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t2_id}/block",
        json={"is_blocked": False, "blocked_by_task_id": t2_id},
    )
    assert self_dep.status_code == 400
