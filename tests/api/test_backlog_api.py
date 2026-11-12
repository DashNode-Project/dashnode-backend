"""API tests for EP-06 backlog routes."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.support import DEFAULT_PASSWORD, create_user, login_as


def switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 200, res.text


def _create_project(client: TestClient, db_engine: Engine, mgr_id: str) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Backlog Project",
            "description": "EP-06",
            "priority": "media",
            "manager_id": mgr_id,
        },
    )
    assert resp.status_code == 201
    project_id: str = resp.json()["id"]
    return project_id


def test_epic_and_story_flow(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-backlog@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev-backlog@dashnode.io", role="developer")
    proj_id = _create_project(client, db_engine, mgr_id)

    add_member = client.post(f"/api/v1/projects/{proj_id}/members", json={"user_id": dev_id})
    assert add_member.status_code == 201

    switch_user(client, "dev-backlog@dashnode.io")
    denied_dev = client.post(
        f"/api/v1/projects/{proj_id}/epics",
        json={"name": "Epic X", "description": "", "color": "#3B82F6"},
    )
    assert denied_dev.status_code == 403

    switch_user(client, "mgr-backlog@dashnode.io")

    empty_name = client.post(
        f"/api/v1/projects/{proj_id}/epics",
        json={"name": "  ", "description": ""},
    )
    assert empty_name.status_code == 400
    assert empty_name.json()["error"]["fields"]["name"] == "El nombre de la épica es obligatorio."

    created = client.post(
        f"/api/v1/projects/{proj_id}/epics",
        json={"name": "Autenticación", "description": "Epic demo", "color": "#3B82F6"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["message"] == "Épica creada correctamente."
    epic_id = body["id"]

    updated = client.patch(
        f"/api/v1/epics/{epic_id}",
        json={"name": "Autenticación v2", "description": "Actualizada", "color": "#10B981"},
    )
    assert updated.status_code == 200
    assert updated.json()["message"] == "Épica actualizada correctamente."

    story = client.post(
        f"/api/v1/epics/{epic_id}/user-stories",
        json={
            "title": "Iniciar sesión",
            "user_role": "Como Gerente",
            "reason": "para acceder al sistema",
            "moscow_priority": "must_have",
        },
    )
    assert story.status_code == 201
    assert story.json()["message"] == "Historia de usuario creada correctamente."
    story_id = story.json()["id"]

    points = client.patch(
        f"/api/v1/user-stories/{story_id}/story-points",
        json={"story_points": 5},
    )
    assert points.status_code == 200
    assert points.json()["message"] == "Puntos de historia asignados correctamente."
    assert points.json()["story_points"] == 5

    bad_points = client.patch(
        f"/api/v1/user-stories/{story_id}/story-points",
        json={"story_points": 4},
    )
    assert bad_points.status_code == 400

    task = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "API login", "task_type": "backend", "notes": "JWT"},
    )
    assert task.status_code == 201
    assert task.json()["message"] == "Tarea agregada correctamente."
    task_id = task.json()["id"]

    switch_user(client, "dev-backlog@dashnode.io")
    dev_task = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "UI login", "task_type": "frontend", "notes": ""},
    )
    assert dev_task.status_code == 201
    dev_task_id = dev_task.json()["id"]

    switch_user(client, "mgr-backlog@dashnode.io")

    assign = client.patch(
        f"/api/v1/story-tasks/{task_id}/assignee",
        json={"assignee_id": dev_id},
    )
    assert assign.status_code == 200
    assert assign.json()["message"] == "Responsable asignado correctamente."

    outsider = create_user(db_engine, email="outsider@dashnode.io", role="developer")
    bad_assign = client.patch(
        f"/api/v1/story-tasks/{task_id}/assignee",
        json={"assignee_id": outsider},
    )
    assert bad_assign.status_code == 400
    assert bad_assign.json()["error"]["message"] == (
        "El usuario seleccionado no pertenece al proyecto."
    )

    switch_user(client, "dev-backlog@dashnode.io")
    hours = client.patch(
        f"/api/v1/story-tasks/{task_id}/estimated-hours",
        json={"estimated_hours": "3.5"},
    )
    assert hours.status_code == 200

    switch_user(client, "mgr-backlog@dashnode.io")
    assert hours.json()["message"] == "Horas estimadas registradas correctamente."

    tree = client.get(f"/api/v1/projects/{proj_id}/backlog")
    assert tree.status_code == 200
    data = tree.json()
    assert len(data["epics"]) == 1
    assert len(data["epics"][0]["stories"]) == 1

    switch_user(client, "dev-backlog@dashnode.io")
    deleted = client.delete(f"/api/v1/story-tasks/{dev_task_id}")
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Tarea eliminada correctamente."


def test_time_status_filters_and_my_tasks(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-time@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev-time@dashnode.io", role="developer")
    other_id = create_user(db_engine, email="other-time@dashnode.io", role="developer")
    proj_id = _create_project(client, db_engine, mgr_id)
    assert (
        client.post(f"/api/v1/projects/{proj_id}/members", json={"user_id": dev_id}).status_code
        == 201
    )
    assert (
        client.post(f"/api/v1/projects/{proj_id}/members", json={"user_id": other_id}).status_code
        == 201
    )
    epic = client.post(f"/api/v1/projects/{proj_id}/epics", json={"name": "EP", "description": ""})
    story = client.post(
        f"/api/v1/epics/{epic.json()['id']}/user-stories",
        json={
            "title": "Historia",
            "user_role": "Dev",
            "reason": "para entregar",
            "moscow_priority": "must_have",
        },
    )
    story_id = story.json()["id"]
    mine = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Tarea mia", "task_type": "backend", "notes": "auth"},
    )
    theirs = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Tarea ajena", "task_type": "qa", "notes": ""},
    )
    task_id = mine.json()["id"]
    other_task = theirs.json()["id"]
    client.patch(f"/api/v1/story-tasks/{task_id}/assignee", json={"assignee_id": dev_id})
    client.patch(f"/api/v1/story-tasks/{other_task}/assignee", json={"assignee_id": other_id})

    logged = client.post(
        f"/api/v1/projects/{proj_id}/tasks/{task_id}/time-logs",
        json={"hours_spent": "1.50", "comment": "avance"},
    )
    assert logged.status_code == 201
    assert logged.json()["message"] == "Horas registradas correctamente."
    assert logged.json()["total_logged_hours"] == "1.50"

    invalid = client.post(
        f"/api/v1/projects/{proj_id}/tasks/{task_id}/time-logs",
        json={"hours_spent": "0"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["message"] == "Las horas invertidas deben ser mayores a 0."

    switch_user(client, "dev-time@dashnode.io")
    denied = client.patch(
        f"/api/v1/projects/{proj_id}/tasks/{other_task}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert denied.status_code == 403
    assert (
        denied.json()["error"]["message"] == "Solo puede cambiar el estado de sus propias tareas."
    )

    ok = client.patch(
        f"/api/v1/projects/{proj_id}/tasks/{task_id}/status",
        json={"status": "IN_PROGRESS"},
    )
    assert ok.status_code == 200
    assert ok.json()["message"] == "Estado de la tarea actualizado."

    blocked = client.patch(
        f"/api/v1/projects/{proj_id}/tasks/{task_id}/status",
        json={"status": "CORRECTION"},
    )
    assert blocked.status_code == 400

    tree = client.get(f"/api/v1/projects/{proj_id}/backlog/tree")
    tasks = tree.json()["tasks_by_story"][story_id]
    assert [row["id"] for row in tasks] == [task_id]

    mine_list = client.get("/api/v1/users/me/tasks")
    assert mine_list.status_code == 200
    assert mine_list.json()["tasks"][0]["name"] == "Tarea mia"
    assert "other" not in mine_list.text

    switch_user(client, "mgr-time@dashnode.io")
    still = client.post(
        f"/api/v1/projects/{proj_id}/epics", json={"name": "Otra", "description": ""}
    )
    assert still.status_code == 201
