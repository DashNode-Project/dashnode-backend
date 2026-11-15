"""API integration tests for EP-11 Part 2 (HU_DN_07_102 .. HU_DN_07_105).

@sad AD-08, AD-09, AD-10
@origin [User Stories HU_DN_07_102 .. HU_DN_07_105]
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.infrastructure.models import StoryTaskModel, TaskStatusHistoryModel
from app.modules.fixes.domain import messages
from app.modules.fixes.infrastructure.models import FixModel
from app.modules.notifications.infrastructure.models import NotificationModel
from app.shared.infrastructure.outbox import OutboxEventModel, SqlAlchemyOutboxStore
from tests.support import DEFAULT_PASSWORD, create_user, login_as


def _switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 200, res.text


def _setup_project(client: TestClient, db_engine: Engine) -> tuple[str, str, str, str]:
    """Create project with manager and two active developer members."""
    mgr_id = login_as(client, db_engine, email="mgr-ep11-p2@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1-ep11-p2@dashnode.io", role="developer")
    dev2_id = create_user(db_engine, email="dev2-ep11-p2@dashnode.io", role="developer")

    proj = client.post(
        "/api/v1/projects",
        json={
            "name": "EP11 Lifecycle",
            "description": "Issue task lifecycle",
            "priority": "alta",
            "manager_id": mgr_id,
        },
    )
    assert proj.status_code == 201, proj.text
    project_id = str(proj.json()["id"])
    assert (
        client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev1_id}).status_code
        == 201
    )
    assert (
        client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev2_id}).status_code
        == 201
    )
    return project_id, mgr_id, dev1_id, dev2_id


def _create_assigned_task(
    client: TestClient,
    project_id: str,
    assignee_id: str,
    *,
    status: str = "IN_PROGRESS",
) -> str:
    epic = client.post(f"/api/v1/projects/{project_id}/epics", json={"name": "Epic QA"})
    assert epic.status_code == 201, epic.text
    epic_id = str(epic.json()["id"])

    story = client.post(
        f"/api/v1/epics/{epic_id}/user-stories",
        json={
            "title": "Historia QA",
            "user_role": "Usuario",
            "reason": "Probar flujo fix",
            "epic_id": epic_id,
        },
    )
    assert story.status_code == 201, story.text
    story_id = str(story.json()["id"])

    task = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Validar sesión OAuth", "task_type": "backend"},
    )
    assert task.status_code == 201, task.text
    task_id = str(task.json()["id"])

    assign = client.patch(
        f"/api/v1/story-tasks/{task_id}/assignee",
        json={"assignee_id": assignee_id},
    )
    assert assign.status_code == 200, assign.text

    if status != "TODO":
        moved = client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/status",
            json={"status": status},
        )
        assert moved.status_code == 200, moved.text

    return task_id


def test_hu_102_assign_issue_rules_optimistic_lock_and_outbox(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, mgr_id, dev1_id, _dev2_id = _setup_project(client, db_engine)
    outsider_dev = create_user(db_engine, email="outsider-p2@dashnode.io", role="developer")
    inactive_dev = create_user(db_engine, email="inactive-p2@dashnode.io", role="developer")
    assert (
        client.post(
            f"/api/v1/projects/{project_id}/members", json={"user_id": inactive_dev}
        ).status_code
        == 201
    )
    with Session(db_engine) as s:
        u = s.get(UserModel, inactive_dev)
        assert u is not None
        u.is_active = False
        s.commit()

    created = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Falla asignación",
            "description": "Detalle",
            "severity": "Alta",
            "type": "Bug",
        },
    )
    assert created.status_code == 201, created.text
    issue_data = created.json()["issue"]
    issue_id = str(issue_data["id"])
    assert issue_data["version"] == 1

    # Developer cannot assign issues
    _switch_user(client, "dev1-ep11-p2@dashnode.io")
    res_dev = client.patch(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/assignee",
        json={"assignee_id": dev1_id, "version": 1},
    )
    assert res_dev.status_code == 403
    assert messages.ASSIGN_FORBIDDEN in res_dev.text

    # Manager validations: non-developer / outsider / inactive rejected
    _switch_user(client, "mgr-ep11-p2@dashnode.io")
    for invalid_target in (mgr_id, outsider_dev, inactive_dev):
        res_bad = client.patch(
            f"/api/v1/projects/{project_id}/issues/{issue_id}/assignee",
            json={"assignee_id": invalid_target, "version": 1},
        )
        assert res_bad.status_code == 400
        assert messages.ASSIGN_DEVELOPER_ONLY in res_bad.text

    # Successful assignment increments version and creates outbox + notification
    res_ok = client.patch(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/assignee",
        json={"assignee_id": dev1_id, "version": 1},
    )
    assert res_ok.status_code == 200, res_ok.text
    assert res_ok.json()["message"] == messages.ISSUE_ASSIGNED
    assert res_ok.json()["issue"]["assignee_id"] == dev1_id
    assert res_ok.json()["issue"]["version"] == 2

    # Optimistic concurrency conflict with stale version -> 409
    res_stale = client.patch(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/assignee",
        json={"assignee_id": None, "version": 1},
    )
    assert res_stale.status_code == 409
    assert messages.OPTIMISTIC_LOCK_CONFLICT in res_stale.text

    # Unassign with current version succeeds
    res_unassign = client.patch(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/assignee",
        json={"assignee_id": None, "version": 2},
    )
    assert res_unassign.status_code == 200
    assert res_unassign.json()["issue"]["assignee_id"] is None
    assert res_unassign.json()["issue"]["version"] == 3

    with Session(db_engine) as s:
        events = s.scalars(
            select(OutboxEventModel).where(
                OutboxEventModel.aggregate_id == issue_id,
                OutboxEventModel.event_type == "issue.assigned",
            )
        ).all()
        assert len(events) == 2
        notifs = s.scalars(
            select(NotificationModel).where(NotificationModel.recipient_id == dev1_id)
        ).all()
        assert len(notifs) >= 1


def test_hu_103_resolve_and_close_issue_lifecycle(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, dev1_id, _dev2_id = _setup_project(client, db_engine)
    admin_id = create_user(db_engine, email="admin-ep11-p2@dashnode.io", role="admin")

    _switch_user(client, "dev1-ep11-p2@dashnode.io")
    created = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Error 500 al exportar",
            "description": "Stacktrace adjunto",
            "severity": "Crítica",
            "type": "Bug",
        },
    )
    assert created.status_code == 201
    issue_id = str(created.json()["issue"]["id"])

    # Validation errors on resolution note
    res_empty = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/resolve",
        json={"resolution_note": "   ", "version": 1},
    )
    assert res_empty.status_code == 400
    assert messages.RESOLUTION_NOTE_REQUIRED in res_empty.text

    res_long = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/resolve",
        json={"resolution_note": "x" * 2001, "version": 1},
    )
    assert res_long.status_code == 400
    assert messages.RESOLUTION_NOTE_TOO_LONG in res_long.text

    # Resolve succeeds
    res_resolve = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/resolve",
        json={"resolution_note": "  Corregido timeout de consulta  ", "version": 1},
    )
    assert res_resolve.status_code == 200, res_resolve.text
    body = res_resolve.json()
    assert body["message"] == messages.ISSUE_RESOLVED
    assert body["issue"]["status"] == "resolved"
    assert body["issue"]["resolution_note"] == "Corregido timeout de consulta"
    assert body["issue"]["resolved_by"] == dev1_id
    assert body["issue"]["resolved_at"] is not None
    assert body["issue"]["version"] == 2

    # Already resolved -> cannot resolve again
    res_again = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/resolve",
        json={"resolution_note": "Otro intento", "version": 2},
    )
    assert res_again.status_code == 400
    assert messages.ISSUE_NOT_OPEN in res_again.text

    # Developer cannot close
    res_dev_close = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/close",
        json={"version": 2},
    )
    assert res_dev_close.status_code == 403
    assert messages.CLOSE_FORBIDDEN in res_dev_close.text

    # Stale version conflict on close
    _switch_user(client, "admin-ep11-p2@dashnode.io")
    assert admin_id
    res_stale = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/close",
        json={"version": 1},
    )
    assert res_stale.status_code == 409
    assert messages.OPTIMISTIC_LOCK_CONFLICT in res_stale.text

    # Admin closes issue
    res_close = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/close",
        json={"version": 2},
    )
    assert res_close.status_code == 200, res_close.text
    assert res_close.json()["message"] == messages.ISSUE_CLOSED
    assert res_close.json()["issue"]["status"] == "closed"
    assert res_close.json()["issue"]["version"] == 3

    with Session(db_engine) as s:
        ev_types = {
            e.event_type
            for e in s.scalars(
                select(OutboxEventModel).where(OutboxEventModel.aggregate_id == issue_id)
            ).all()
        }
        assert {"issue.resolved", "issue.closed"} <= ev_types


def test_hu_104_report_fix_atomic_and_fault_injection_rollback(
    client: TestClient, db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, mgr_id, dev1_id, dev2_id = _setup_project(client, db_engine)
    assert dev2_id
    task_id = _create_assigned_task(client, project_id, dev1_id, status="CODE_REVIEW")

    # Non-owner developer rejected
    _switch_user(client, "dev2-ep11-p2@dashnode.io")
    res_forbidden = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={
            "title": "Fix: Validar sesión OAuth",
            "description": "Token expira antes",
            "severity": "Alta",
            "type": "Bug",
        },
    )
    assert res_forbidden.status_code == 403
    assert messages.FIX_REPORT_OWN_TASKS_ONLY in res_forbidden.text

    # Fault injection: outbox failure rolls back task status, status_before_correction, and fix
    _switch_user(client, "dev1-ep11-p2@dashnode.io")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Simulated outbox DB fault")

    monkeypatch.setattr(SqlAlchemyOutboxStore, "enqueue_event", _boom)
    with pytest.raises(RuntimeError, match="Simulated outbox DB fault"):
        client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
            json={
                "title": "Fix: Validar sesión OAuth",
                "description": "Fallo atómico",
                "severity": "Alta",
                "type": "Bug",
            },
        )
    monkeypatch.undo()

    with Session(db_engine) as s:
        task_row = s.get(StoryTaskModel, task_id)
        assert task_row is not None
        assert task_row.status == "CODE_REVIEW"
        assert task_row.status_before_correction is None
        assert s.scalars(select(FixModel).where(FixModel.task_id == task_id)).all() == []
        assert s.scalars(select(OutboxEventModel)).all() == []

    # Happy path with idempotency key
    res_fix1 = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={
            "title": "Fix: Validar sesión OAuth",
            "description": "Error en refresh token",
            "severity": "Alta",
            "type": "Bug",
            "idempotency_key": "idem-fix-1",
        },
    )
    assert res_fix1.status_code == 201, res_fix1.text
    b1 = res_fix1.json()
    assert b1["message"] == messages.TASK_FIX_REPORTED
    assert b1["task_status"] == "CORRECTION"
    assert b1["issue"]["task_id"] == task_id
    assert b1["issue"]["task_status"] == "CORRECTION"
    assert b1["issue"]["task_previous_status"] == "CODE_REVIEW"
    fix1_id = str(b1["issue"]["id"])

    # Replay idempotency key does not duplicate fix
    res_replay = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={
            "title": "Fix: Validar sesión OAuth",
            "description": "Error en refresh token",
            "severity": "Alta",
            "type": "Bug",
            "idempotency_key": "idem-fix-1",
        },
    )
    assert res_replay.status_code == 201
    assert res_replay.json()["issue"]["id"] == fix1_id

    # Reporting a SECOND fix on already-CORRECTION task preserves status_before_correction
    _switch_user(client, "mgr-ep11-p2@dashnode.io")
    res_fix2 = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={
            "title": "Fix: Segundo fallo en OAuth",
            "description": "Header faltante",
            "severity": "Media",
            "type": "Regresión",
        },
    )
    assert res_fix2.status_code == 201, res_fix2.text

    detail1 = client.get(f"/api/v1/projects/{project_id}/issues/{fix1_id}")
    assert detail1.status_code == 200
    assert detail1.json()["other_open_issues_count"] == 1

    with Session(db_engine) as s:
        task_row = s.get(StoryTaskModel, task_id)
        assert task_row is not None
        assert task_row.status == "CORRECTION"
        assert task_row.status_before_correction == "CODE_REVIEW"
        assert task_row.version == 3
        hist = s.scalars(
            select(TaskStatusHistoryModel).where(TaskStatusHistoryModel.task_id == task_id)
        ).all()
        assert any(
            h.previous_status == "CODE_REVIEW" and h.new_status == "CORRECTION" for h in hist
        )
        mgr_notifs = s.scalars(
            select(NotificationModel).where(NotificationModel.recipient_id == mgr_id)
        ).all()
        assert len(mgr_notifs) >= 1


def test_hu_105_unlink_and_restore_task_only_after_last_issue(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _mgr_id, dev1_id, _dev2_id = _setup_project(client, db_engine)
    task_id = _create_assigned_task(client, project_id, dev1_id, status="CODE_REVIEW")

    _switch_user(client, "dev1-ep11-p2@dashnode.io")
    r1 = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={"title": "Fix 1", "description": "Uno", "severity": "Alta", "type": "Bug"},
    )
    r2 = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/report-fix",
        json={"title": "Fix 2", "description": "Dos", "severity": "Baja", "type": "UX"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    fix1_id = str(r1.json()["issue"]["id"])
    fix2_id = str(r2.json()["issue"]["id"])

    # Resolving Fix 1 while Fix 2 is still open leaves task in CORRECTION
    res_first = client.post(
        f"/api/v1/projects/{project_id}/issues/{fix1_id}/resolve",
        json={"resolution_note": "Fix 1 listo", "task_status": "TESTING", "version": 1},
    )
    assert res_first.status_code == 200, res_first.text
    assert res_first.json()["message"] == messages.ISSUE_RESOLVED
    assert res_first.json()["task_unlinked"] is False
    assert res_first.json()["task_status"] == "CORRECTION"

    # Now Fix 2 sees 0 other open issues
    det2 = client.get(f"/api/v1/projects/{project_id}/issues/{fix2_id}")
    assert det2.status_code == 200
    assert det2.json()["other_open_issues_count"] == 0
    assert det2.json()["task_previous_status"] == "CODE_REVIEW"

    # Resolving last issue without explicit task_status restores previous_status ("CODE_REVIEW")
    res_last = client.post(
        f"/api/v1/projects/{project_id}/issues/{fix2_id}/resolve",
        json={"resolution_note": "Fix 2 listo", "version": 1},
    )
    assert res_last.status_code == 200, res_last.text
    body = res_last.json()
    assert messages.ISSUE_RESOLVED in body["message"]
    assert messages.TASK_UNLINKED_AND_UPDATED in body["message"]
    assert body["task_unlinked"] is True
    assert body["task_status"] == "CODE_REVIEW"
    assert body["task_message"] == messages.TASK_UNLINKED_AND_UPDATED

    with Session(db_engine) as s:
        task_row = s.get(StoryTaskModel, task_id)
        assert task_row is not None
        assert task_row.status == "CODE_REVIEW"
        assert task_row.status_before_correction is None
        assert task_row.version == 4
        restored_ev = s.scalars(
            select(OutboxEventModel).where(
                OutboxEventModel.aggregate_id == task_id,
                OutboxEventModel.event_type == "task.status_restored",
            )
        ).all()
        assert len(restored_ev) == 1

    # Also test explicit chosen target status ("TESTING") on another task
    _switch_user(client, "mgr-ep11-p2@dashnode.io")
    task2_id = _create_assigned_task(client, project_id, dev1_id, status="TODO")
    r3 = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task2_id}/report-fix",
        json={"title": "Fix 3", "description": "Tres", "severity": "Media", "type": "Bug"},
    )
    assert r3.status_code == 201
    fix3_id = str(r3.json()["issue"]["id"])
    res_explicit = client.post(
        f"/api/v1/projects/{project_id}/issues/{fix3_id}/resolve",
        json={"resolution_note": "Resuelto directo", "task_status": "TESTING", "version": 1},
    )
    assert res_explicit.status_code == 200
    assert res_explicit.json()["task_status"] == "TESTING"

    # Also test fallback to IN_PROGRESS when status_before_correction is missing/null
    task3_id = _create_assigned_task(client, project_id, dev1_id, status="TODO")
    r4 = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task3_id}/report-fix",
        json={"title": "Fix 4", "description": "Cuatro", "severity": "Baja", "type": "Bug"},
    )
    assert r4.status_code == 201
    fix4_id = str(r4.json()["issue"]["id"])
    with Session(db_engine) as s:
        t3 = s.get(StoryTaskModel, task3_id)
        assert t3 is not None
        t3.status_before_correction = None
        s.commit()

    res_fallback = client.post(
        f"/api/v1/projects/{project_id}/issues/{fix4_id}/resolve",
        json={"resolution_note": "Resuelto con fallback", "version": 1},
    )
    assert res_fallback.status_code == 200
    assert res_fallback.json()["task_unlinked"] is True
    assert res_fallback.json()["task_status"] == "IN_PROGRESS"
