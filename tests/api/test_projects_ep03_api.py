"""
API tests for EP-03 project lifecycle (HU_DN_02_22 .. HU_DN_02_26).
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from app.modules.projects.infrastructure.models import AuditLogModel, ProjectModel
from app.modules.tasks.infrastructure.models import TaskModel
from tests.support import create_user, login_as


def _create_payload(manager_id: str) -> dict[str, object]:
    return {
        "name": "Proyecto Alpha",
        "description": "Descripción",
        "priority": "media",
        "tech_stack": ["Python", "React"],
        "meeting_link": "https://meet.example.com/room",
        "manager_id": manager_id,
    }


def test_hu_22_create_project_manager(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr@dashnode.io", role="manager")
    resp = client.post("/api/v1/projects", json=_create_payload(mgr_id))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Proyecto Alpha"
    assert data["status"] == "planificacion"
    assert data["manager_id"] == mgr_id


def test_hu_22_developer_cannot_create(client: TestClient, db_engine: Engine) -> None:
    mgr_id = create_user(db_engine, email="mgr2@dashnode.io", role="manager")
    login_as(client, db_engine, email="dev@dashnode.io", role="developer")
    resp = client.post("/api/v1/projects", json=_create_payload(mgr_id))
    assert resp.status_code == 403


def test_hu_22_admin_cannot_create(client: TestClient, db_engine: Engine) -> None:
    mgr_id = create_user(db_engine, email="mgr-admin-block@dashnode.io", role="manager")
    login_as(client, db_engine, email="admin-block@dashnode.io", role="admin")
    resp = client.post("/api/v1/projects", json=_create_payload(mgr_id))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"


def test_hu_22_validation_messages(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr3@dashnode.io", role="manager")
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "",
            "manager_id": mgr_id,
            "meeting_link": "bad",
        },
    )
    assert resp.status_code == 400
    fields = resp.json()["error"]["fields"]
    assert fields["name"] == "El nombre del proyecto es obligatorio."
    assert fields["meeting_link"] == "El enlace de reunión no tiene un formato de URL válido."


def test_hu_23_update_project(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr4@dashnode.io", role="manager")
    created = client.post("/api/v1/projects", json=_create_payload(mgr_id)).json()
    patch = client.patch(
        f"/api/v1/projects/{created['id']}",
        json={
            "name": "Proyecto Beta",
            "description": "Nueva desc",
            "priority": "alta",
            "tech_stack": ["Go"],
            "meeting_link": None,
        },
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Proyecto Beta"


def test_hu_24_status_update(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr5@dashnode.io", role="manager")
    created = client.post("/api/v1/projects", json=_create_payload(mgr_id)).json()
    ok = client.patch(
        f"/api/v1/projects/{created['id']}/status",
        json={"status": "activo"},
    )
    assert ok.status_code == 200
    assert ok.json()["message"] == "Estado del proyecto actualizado."

    bad = client.patch(
        f"/api/v1/projects/{created['id']}/status",
        json={"status": "invalido"},
    )
    assert bad.status_code == 422 or bad.status_code == 400


def test_hu_25_assign_manager(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="other-mgr@dashnode.io", role="manager")
    created = client.post(
        "/api/v1/projects",
        json=_create_payload(mgr_id),
    ).json()
    resp = client.patch(
        f"/api/v1/projects/{created['id']}/manager",
        json={"manager_id": mgr_id},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Gerente responsable actualizado correctamente."


def test_hu_26_manager_soft_delete(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr-del@dashnode.io", role="manager")
    created = client.post("/api/v1/projects", json=_create_payload(mgr_id)).json()
    proj_id = created["id"]

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    task_id = "task-soft-1"
    session = sessionmaker(bind=db_engine)()
    try:
        session.add(
            TaskModel(
                id=task_id,
                project_id=proj_id,
                title="Tarea seed",
                description="",
                status="todo",
                priority="low",
                assignee_id=None,
                creator_id=mgr_id,
                has_open_fix=False,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    del_resp = client.delete(f"/api/v1/projects/{proj_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Proyecto eliminado correctamente."

    assert client.get(f"/api/v1/projects/{proj_id}").status_code == 404

    session = sessionmaker(bind=db_engine)()
    try:
        proj = session.get(ProjectModel, proj_id)
        assert proj is not None
        assert proj.deleted_at is not None
        task = session.get(TaskModel, task_id)
        assert task is not None
        assert task.deleted_at is not None
        audits = session.scalars(select(AuditLogModel)).all()
        assert any(a.action == "project.deleted" for a in audits)
    finally:
        session.close()
