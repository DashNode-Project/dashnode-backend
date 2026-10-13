"""
Integration and API tests for EP-05: Agendamiento y reuniones.
Covers HU_DN_03_37, HU_DN_03_38, HU_DN_03_39, HU_DN_03_40, HU_DN_03_41.
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from app.modules.availability.domain import messages
from app.modules.notifications.infrastructure.models import NotificationModel
from tests.support import DEFAULT_PASSWORD, create_user, login_as


def switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post("/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD})
    assert res.status_code == 200, res.text


def _setup_project_with_members(
    client: TestClient,
    mgr_id: str,
    dev_ids: list[str],
    project_name: str = "Proyecto Beta",
) -> str:
    res = client.post(
        "/api/v1/projects",
        json={
            "name": project_name,
            "description": "Beta project description",
            "priority": "alta",
            "tech_stack": ["FastAPI", "React"],
            "meeting_link": "https://meet.google.com/test-room",
            "manager_id": mgr_id,
        },
    )
    assert res.status_code == 201, res.text
    project_id = str(res.json()["id"])
    for d_id in dev_ids:
        add_res = client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"user_id": d_id},
        )
        assert add_res.status_code == 201
    return project_id


# =========================================================================
# HU_DN_03_37 & HU_DN_03_38: Agendar reunión (Validaciones y Creación)
# =========================================================================


def test_hu_38_managed_projects_list(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin_ep05@dashnode.io", role="admin")
    mgr_id = create_user(db_engine, email="mgr_ep05@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_ep05@dashnode.io", role="developer")

    # Admin creates project managed by mgr
    p1 = _setup_project_with_members(client, mgr_id, [dev_id], "Proyecto 1")

    # Developer gets 403 on managed projects
    switch_user(client, "dev_ep05@dashnode.io")
    res_dev = client.get("/api/v1/availability/projects")
    assert res_dev.status_code == 403

    # Manager sees project 1
    switch_user(client, "mgr_ep05@dashnode.io")
    res_mgr = client.get("/api/v1/availability/projects")
    assert res_mgr.status_code == 200
    projs_mgr = res_mgr.json()
    assert any(p["id"] == p1 for p in projs_mgr)

    # Admin sees all projects
    switch_user(client, "admin_ep05@dashnode.io")
    res_adm = client.get("/api/v1/availability/projects")
    assert res_adm.status_code == 200
    assert any(p["id"] == p1 for p in res_adm.json())


def test_hu_38_create_meeting_validations(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_val@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1_val@dashnode.io", role="developer")
    outsider_id = create_user(db_engine, email="dev_out@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev1_id], "Proyecto Validaciones")

    base_payload = {
        "title": "Daily Standup",
        "type": "Daily",
        "project_id": p_id,
        "date": "2026-10-15",
        "start_time": "09:00",
        "end_time": "09:30",
        "duration": 30,
        "link": "https://meet.google.com/room-val",
        "participant_ids": [dev1_id],
    }

    # 1. Missing title
    payload = dict(base_payload, title="")
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["message"] == messages.MEETING_TITLE_REQUIRED

    # 2. Missing/invalid type
    payload = dict(base_payload, type="")
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["message"] == messages.MEETING_TYPE_REQUIRED

    payload = dict(base_payload, type="InvalidType")
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["message"] == messages.MEETING_TYPE_REQUIRED

    # 3. Missing project
    payload = dict(base_payload, project_id="")
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["message"] == messages.PROJECT_REQUIRED

    # 4. Participants must be project members
    payload = dict(base_payload, participant_ids=[dev1_id, outsider_id])
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["message"] == messages.PARTICIPANTS_MUST_BE_PROJECT_MEMBERS

    # 5. Invalid meeting link format
    payload = dict(base_payload, link="not-a-valid-url")
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 400
    assert res.json()["error"]["message"] == messages.INVALID_MEETING_LINK

    # 6. Developer cannot create meeting
    switch_user(client, "dev1_val@dashnode.io")
    res_dev = client.post("/api/v1/availability/meetings", json=base_payload)
    assert res_dev.status_code == 403


def test_hu_38_successful_meeting_creation_and_notifications(
    client: TestClient, db_engine: Engine
) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_sched@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_sched@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "Proyecto Notif")

    payload = {
        "title": "Sprint Review Epica 05",
        "type": "Review",
        "project_id": p_id,
        "date": "2026-10-16",
        "start_time": "14:00",
        "end_time": "15:00",
        "duration": 60,
        "link": "https://meet.google.com/review-room",
        "participant_ids": [dev_id],
    }
    res = client.post("/api/v1/availability/meetings", json=payload)
    assert res.status_code == 201, res.text
    meeting = res.json()
    assert meeting["title"] == "Sprint Review Epica 05"
    assert meeting["type"] == "Review"
    assert meeting["status"] == "scheduled"
    assert meeting["project_name"] == "Proyecto Notif"
    assert len(meeting["participants"]) == 1
    assert meeting["participants"][0]["user_id"] == dev_id
    assert meeting["participants"][0]["response"] == "pendiente"

    # Check notification dispatched to dev_id
    session_maker = sessionmaker(bind=db_engine)
    with session_maker() as session:
        notif = session.scalars(
            select(NotificationModel).where(
                NotificationModel.recipient_id == dev_id,
                NotificationModel.type == "meeting_scheduled",
            )
        ).first()
        assert notif is not None
        assert "Sprint Review Epica 05" in notif.title


def test_hu_38_concurrent_meeting_conflict(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_concur@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_concur@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "Proyecto Concurrencia")

    # Schedule first meeting from 10:00 to 11:00
    res1 = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Reunión 1",
            "type": "General",
            "project_id": p_id,
            "date": "2026-10-17",
            "start_time": "10:00",
            "end_time": "11:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res1.status_code == 201

    # Attempt overlapping meeting (10:30 to 11:30) with dev_id
    res_conflict = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Reunión Traslapada",
            "type": "General",
            "project_id": p_id,
            "date": "2026-10-17",
            "start_time": "10:30",
            "end_time": "11:30",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["message"] == messages.PARTICIPANT_MEETING_CONFLICT


# =========================================================================
# HU_DN_03_39 & HU_DN_03_40: Listar reuniones y Filtros
# =========================================================================


def test_hu_39_meetings_list_role_scoping(client: TestClient, db_engine: Engine) -> None:
    mgr1_id = login_as(client, db_engine, email="mgr_scope1@dashnode.io", role="manager")
    create_user(db_engine, email="admin_scope@dashnode.io", role="admin")
    dev1_id = create_user(db_engine, email="dev_scope1@dashnode.io", role="developer")
    create_user(db_engine, email="dev_scope2@dashnode.io", role="developer")
    p1_id = _setup_project_with_members(client, mgr1_id, [dev1_id], "P1 Scoping")

    # mgr1 creates meeting for dev1
    res1 = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Meeting P1 Dev1",
            "type": "Planning",
            "project_id": p1_id,
            "date": "2026-10-20",
            "start_time": "09:00",
            "end_time": "10:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev1_id],
        },
    )
    assert res1.status_code == 201
    m1_id = res1.json()["id"]

    # dev1 logs in and sees m1
    switch_user(client, "dev_scope1@dashnode.io")
    res_dev1 = client.get("/api/v1/availability/meetings")
    assert res_dev1.status_code == 200
    assert any(m["id"] == m1_id for m in res_dev1.json())

    # dev2 logs in and does NOT see m1 (not a participant)
    switch_user(client, "dev_scope2@dashnode.io")
    res_dev2 = client.get("/api/v1/availability/meetings")
    assert res_dev2.status_code == 200
    assert not any(m["id"] == m1_id for m in res_dev2.json())

    # admin sees m1
    switch_user(client, "admin_scope@dashnode.io")
    res_admin = client.get("/api/v1/availability/meetings")
    assert res_admin.status_code == 200
    assert any(m["id"] == m1_id for m in res_admin.json())


def test_hu_39_filter_upcoming_and_past(client: TestClient, db_engine: Engine) -> None:
    login_as(client, db_engine, email="admin_filter@dashnode.io", role="admin")
    mgr_id = create_user(db_engine, email="mgr_filter@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_filter@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "P Filter")

    # Meeting in the future
    res_up = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Futura",
            "type": "Retro",
            "project_id": p_id,
            "date": "2026-12-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res_up.status_code == 201

    # Meeting in the past
    res_past = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Pasada",
            "type": "Daily",
            "project_id": p_id,
            "date": "2026-01-01",
            "start_time": "10:00",
            "end_time": "10:30",
            "duration": 30,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res_past.status_code == 201

    # Filter upcoming
    res = client.get("/api/v1/availability/meetings?filter_type=upcoming")
    assert res.status_code == 200
    titles = [m["title"] for m in res.json()]
    assert "Futura" in titles
    assert "Pasada" not in titles

    # Filter past
    res = client.get("/api/v1/availability/meetings?filter_type=past")
    assert res.status_code == 200
    titles = [m["title"] for m in res.json()]
    assert "Pasada" in titles
    assert "Futura" not in titles


# =========================================================================
# HU_DN_03_41: Detalle, Cancelar, Responder y Registrar Minuta
# =========================================================================


def test_hu_41_meeting_detail_and_access_control(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_det@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1_det@dashnode.io", role="developer")
    create_user(db_engine, email="stranger@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev1_id], "P Detalle")

    res = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Detalle Sync",
            "type": "Planning",
            "project_id": p_id,
            "date": "2026-10-25",
            "start_time": "11:00",
            "end_time": "12:00",
            "duration": 60,
            "link": "https://meet.google.com/xyz",
            "participant_ids": [dev1_id],
        },
    )
    assert res.status_code == 201
    m_id = res.json()["id"]

    # Dev1 (participant) can view detail
    switch_user(client, "dev1_det@dashnode.io")
    res_det = client.get(f"/api/v1/availability/meetings/{m_id}")
    assert res_det.status_code == 200
    data = res_det.json()
    assert data["id"] == m_id
    assert data["title"] == "Detalle Sync"
    assert data["link"] == "https://meet.google.com/xyz"
    assert len(data["participants"]) == 1

    # Stranger developer gets 403
    switch_user(client, "stranger@dashnode.io")
    res_stranger = client.get(f"/api/v1/availability/meetings/{m_id}")
    assert res_stranger.status_code == 403


def test_hu_41_participant_respond_meeting(client: TestClient, db_engine: Engine) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_resp@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_resp@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "P Respond")

    res = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Respuesta Test",
            "type": "General",
            "project_id": p_id,
            "date": "2026-10-26",
            "start_time": "15:00",
            "end_time": "16:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res.status_code == 201
    m_id = res.json()["id"]

    # Developer responds 'aceptada'
    switch_user(client, "dev_resp@dashnode.io")
    resp_res = client.post(
        f"/api/v1/availability/meetings/{m_id}/respond",
        json={"response": "aceptada"},
    )
    assert resp_res.status_code == 200
    part_resp = next(p for p in resp_res.json()["participants"] if p["user_id"] == dev_id)
    assert part_resp["response"] == "aceptada"

    # Developer changes to 'rechazada'
    resp_res2 = client.post(
        f"/api/v1/availability/meetings/{m_id}/respond",
        json={"response": "rechazada"},
    )
    assert resp_res2.status_code == 200
    part_resp2 = next(p for p in resp_res2.json()["participants"] if p["user_id"] == dev_id)
    assert part_resp2["response"] == "rechazada"


def test_hu_41_cancel_meeting_and_summary_registration(
    client: TestClient, db_engine: Engine
) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_acta@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_acta@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "P Minuta")

    res = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Minuta Test",
            "type": "Retro",
            "project_id": p_id,
            "date": "2026-01-01",
            "start_time": "16:00",
            "end_time": "17:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res.status_code == 201
    m_id = res.json()["id"]

    # Developer cannot register summary or cancel
    switch_user(client, "dev_acta@dashnode.io")
    res_dev_sum = client.post(
        f"/api/v1/availability/meetings/{m_id}/summary",
        json={"summary": "Resumen dev", "minutes_url": "https://docs.google.com/doc1"},
    )
    assert res_dev_sum.status_code == 403

    res_dev_can = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_dev_can.status_code == 403

    # Creator (manager) registers summary and minutes_url
    switch_user(client, "mgr_acta@dashnode.io")
    res_mgr_sum = client.post(
        f"/api/v1/availability/meetings/{m_id}/summary",
        json={
            "summary": "Acuerdos del sprint: continuar con integraciones.",
            "minutes_url": "https://docs.google.com/document/d/abc-123",
        },
    )
    assert res_mgr_sum.status_code == 200
    m_data = res_mgr_sum.json()
    assert m_data["summary"] == "Acuerdos del sprint: continuar con integraciones."
    assert m_data["minutes_url"] == "https://docs.google.com/document/d/abc-123"
    assert m_data["status"] == "completed"

    # Creator cancels meeting
    res_can = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_can.status_code == 200
    assert res_can.json()["status"] == "cancelled"


# =========================================================================
# HU_DN_03_42: Enviar reunión a Google Calendar / Detalle de reunión
# =========================================================================


def test_hu_42_meeting_detail_and_google_calendar_data(
    client: TestClient, db_engine: Engine
) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_hu42@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_hu42@dashnode.io", role="developer")
    create_user(db_engine, email="outsider_hu42@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "P HU42")

    res = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Sprint Review con Cliente",
            "type": "Review",
            "project_id": p_id,
            "date": "2026-11-20",
            "start_time": "10:00",
            "end_time": "11:00",
            "duration": 60,
            "link": "https://meet.google.com/hu42-room",
            "participant_ids": [dev_id],
        },
    )
    assert res.status_code == 201
    m_id = res.json()["id"]

    # 1. Detail returns all necessary fields to construct Google Calendar entry
    switch_user(client, "dev_hu42@dashnode.io")
    res_det = client.get(f"/api/v1/availability/meetings/{m_id}")
    assert res_det.status_code == 200
    data = res_det.json()
    assert data["title"] == "Sprint Review con Cliente"
    assert data["date"] == "2026-11-20"
    assert data["start_time"] == "10:00"
    assert data["end_time"] == "11:00"
    assert data["duration"] == 60
    assert data["link"] == "https://meet.google.com/hu42-room"
    assert data["project_name"] == "P HU42"
    assert len(data["participants"]) >= 1
    assert any(p["email"] == "dev_hu42@dashnode.io" for p in data["participants"])

    # 2. Access control: outsider developer gets 403
    switch_user(client, "outsider_hu42@dashnode.io")
    res_out = client.get(f"/api/v1/availability/meetings/{m_id}")
    assert res_out.status_code == 403
    assert res_out.json()["error"]["code"] == "ACCESS_DENIED"


# =========================================================================
# HU_DN_03_44: Responder convocatoria de reunión
# =========================================================================


def test_hu_44_respond_meeting_lifecycle_and_constraints(
    client: TestClient, db_engine: Engine
) -> None:
    mgr_id = login_as(client, db_engine, email="mgr_hu44@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_hu44@dashnode.io", role="developer")
    create_user(db_engine, email="outsider_hu44@dashnode.io", role="developer")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "P HU44")

    # Meeting scheduled in the future
    res = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Architecture Sync",
            "type": "General",
            "project_id": p_id,
            "date": "2026-11-25",
            "start_time": "14:00",
            "end_time": "15:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res.status_code == 201
    m_id = res.json()["id"]

    # 1. Participant responds 'aceptada'
    switch_user(client, "dev_hu44@dashnode.io")
    res_accept = client.post(
        f"/api/v1/availability/meetings/{m_id}/respond",
        json={"response": "aceptada"},
    )
    assert res_accept.status_code == 200
    part = next(p for p in res_accept.json()["participants"] if p["user_id"] == dev_id)
    assert part["response"] == "aceptada"

    # 2. Participant modifies response to 'rechazada'
    res_reject = client.post(
        f"/api/v1/availability/meetings/{m_id}/respond",
        json={"response": "rechazada"},
    )
    assert res_reject.status_code == 200
    part = next(p for p in res_reject.json()["participants"] if p["user_id"] == dev_id)
    assert part["response"] == "rechazada"

    # 3. Non-participant developer cannot respond (403)
    switch_user(client, "outsider_hu44@dashnode.io")
    res_out = client.post(
        f"/api/v1/availability/meetings/{m_id}/respond",
        json={"response": "aceptada"},
    )
    assert res_out.status_code == 403

    # 4. Cannot respond to cancelled meeting (400 MEETING_CANCELLED)
    switch_user(client, "mgr_hu44@dashnode.io")
    res_cancel = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_cancel.status_code == 200

    switch_user(client, "dev_hu44@dashnode.io")
    res_resp_cancelled = client.post(
        f"/api/v1/availability/meetings/{m_id}/respond",
        json={"response": "aceptada"},
    )
    assert res_resp_cancelled.status_code == 400
    assert res_resp_cancelled.json()["error"]["code"] == "MEETING_CANCELLED"
    assert (
        res_resp_cancelled.json()["error"]["message"] == messages.MEETING_CANCELLED_CANNOT_RESPOND
    )

    # 5. Cannot respond to a meeting already in the past (400 MEETING_ALREADY_PAST)
    switch_user(client, "mgr_hu44@dashnode.io")
    res_past = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Daily Antigua",
            "type": "Daily",
            "project_id": p_id,
            "date": "2026-01-01",
            "start_time": "08:00",
            "end_time": "08:30",
            "duration": 30,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res_past.status_code == 201
    past_m_id = res_past.json()["id"]

    switch_user(client, "dev_hu44@dashnode.io")
    res_resp_past = client.post(
        f"/api/v1/availability/meetings/{past_m_id}/respond",
        json={"response": "aceptada"},
    )
    assert res_resp_past.status_code == 400
    assert res_resp_past.json()["error"]["code"] == "MEETING_ALREADY_PAST"
    assert res_resp_past.json()["error"]["message"] == messages.MEETING_ALREADY_PAST


# =========================================================================
# HU_DN_03_45: Cancelar reunión programada y RN-AGE-05
# =========================================================================


def test_hu_45_cancel_meeting_and_notifications_and_rn_age_05(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email="admin_hu45@dashnode.io", role="admin")
    mgr_id = create_user(db_engine, email="mgr_hu45@dashnode.io", role="manager")
    create_user(db_engine, email="other_mgr_hu45@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1_hu45@dashnode.io", role="developer")
    dev2_id = create_user(db_engine, email="dev2_hu45@dashnode.io", role="developer")

    switch_user(client, "mgr_hu45@dashnode.io")
    p_id = _setup_project_with_members(client, mgr_id, [dev1_id, dev2_id], "P HU45")

    # Manager creates meeting with dev1 and dev2
    res = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Release Planning",
            "type": "Planning",
            "project_id": p_id,
            "date": "2026-11-28",
            "start_time": "16:00",
            "end_time": "17:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev1_id, dev2_id],
        },
    )
    assert res.status_code == 201
    m_id = res.json()["id"]

    # RN-AGE-05 Constraint: Admin CANNOT cancel manager's meeting (403 ONLY_CREATOR_CAN_CANCEL)
    switch_user(client, "admin_hu45@dashnode.io")
    res_admin_cancel = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_admin_cancel.status_code == 403
    assert res_admin_cancel.json()["error"]["code"] == "ONLY_CREATOR_CAN_CANCEL"
    assert res_admin_cancel.json()["error"]["message"] == messages.ONLY_CREATOR_CAN_CANCEL

    # Other manager cannot cancel (403)
    switch_user(client, "other_mgr_hu45@dashnode.io")
    res_other_cancel = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_other_cancel.status_code == 403
    assert res_other_cancel.json()["error"]["code"] == "ONLY_CREATOR_CAN_CANCEL"

    # Developer cannot cancel (403)
    switch_user(client, "dev1_hu45@dashnode.io")
    res_dev_cancel = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_dev_cancel.status_code == 403
    assert res_dev_cancel.json()["error"]["code"] == "ONLY_CREATOR_CAN_CANCEL"

    # Creator (manager) cancels meeting (200)
    switch_user(client, "mgr_hu45@dashnode.io")
    res_cancel = client.post(f"/api/v1/availability/meetings/{m_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    # Notifications dispatched to participants dev1 and dev2
    session_factory = sessionmaker(bind=db_engine)
    with session_factory() as session:
        notifs_dev1 = session.scalars(
            select(NotificationModel).where(
                NotificationModel.recipient_id == dev1_id,
                NotificationModel.type == "meeting_cancelled",
            )
        ).all()
        assert len(notifs_dev1) >= 1
        assert "Release Planning" in notifs_dev1[0].message

        notifs_dev2 = session.scalars(
            select(NotificationModel).where(
                NotificationModel.recipient_id == dev2_id,
                NotificationModel.type == "meeting_cancelled",
            )
        ).all()
        assert len(notifs_dev2) >= 1
        assert "Release Planning" in notifs_dev2[0].message

    # Cancelled meeting is excluded from upcoming filter
    res_upcoming = client.get("/api/v1/availability/meetings?filter_type=upcoming")
    assert res_upcoming.status_code == 200
    assert not any(m["id"] == m_id for m in res_upcoming.json())


# =========================================================================
# HU_DN_03_46: Registrar resumen y acta de reunión
# =========================================================================


def test_hu_46_meeting_summary_validations_and_lifecycle(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email="admin_hu46@dashnode.io", role="admin")
    mgr_id = create_user(db_engine, email="mgr_hu46@dashnode.io", role="manager")
    dev_id = create_user(db_engine, email="dev_hu46@dashnode.io", role="developer")

    switch_user(client, "mgr_hu46@dashnode.io")
    p_id = _setup_project_with_members(client, mgr_id, [dev_id], "P HU46")

    # 1. Scheduled future meeting cannot have summary registered (400 MEETING_NOT_COMPLETED)
    res_future = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Futura para Acta",
            "type": "General",
            "project_id": p_id,
            "date": "2026-12-15",
            "start_time": "10:00",
            "end_time": "11:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res_future.status_code == 201
    future_id = res_future.json()["id"]

    res_sum_fut = client.post(
        f"/api/v1/availability/meetings/{future_id}/summary",
        json={"summary": "Resumen temprano", "minutes_url": None},
    )
    assert res_sum_fut.status_code == 400
    assert res_sum_fut.json()["error"]["code"] == "MEETING_NOT_COMPLETED"
    assert res_sum_fut.json()["error"]["message"] == messages.MEETING_NOT_COMPLETED

    # 2. Past meeting (eligible for summary)
    res_past = client.post(
        "/api/v1/availability/meetings",
        json={
            "title": "Reunión Realizada",
            "type": "Retro",
            "project_id": p_id,
            "date": "2026-01-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "duration": 60,
            "link": None,
            "participant_ids": [dev_id],
        },
    )
    assert res_past.status_code == 201
    past_id = res_past.json()["id"]

    # Validation: empty summary (400 SUMMARY_REQUIRED)
    res_empty = client.post(
        f"/api/v1/availability/meetings/{past_id}/summary",
        json={"summary": "   ", "minutes_url": None},
    )
    assert res_empty.status_code == 400
    assert res_empty.json()["error"]["code"] == "SUMMARY_REQUIRED"
    assert res_empty.json()["error"]["message"] == messages.SUMMARY_REQUIRED

    # Validation: summary > 2000 chars (400 SUMMARY_TOO_LONG)
    res_long = client.post(
        f"/api/v1/availability/meetings/{past_id}/summary",
        json={"summary": "A" * 2001, "minutes_url": None},
    )
    assert res_long.status_code == 400
    assert res_long.json()["error"]["code"] == "SUMMARY_TOO_LONG"
    assert res_long.json()["error"]["message"] == messages.SUMMARY_TOO_LONG

    # Validation: invalid minutes URL (400 INVALID_MINUTES_URL)
    res_bad_url = client.post(
        f"/api/v1/availability/meetings/{past_id}/summary",
        json={"summary": "Resumen válido", "minutes_url": "ftp://not-a-valid-http-url"},
    )
    assert res_bad_url.status_code == 400
    assert res_bad_url.json()["error"]["code"] == "INVALID_MINUTES_URL"
    assert res_bad_url.json()["error"]["message"] == messages.INVALID_MINUTES_URL

    # Developer cannot register summary (403)
    switch_user(client, "dev_hu46@dashnode.io")
    res_dev_sum = client.post(
        f"/api/v1/availability/meetings/{past_id}/summary",
        json={"summary": "Resumen por dev", "minutes_url": None},
    )
    assert res_dev_sum.status_code == 403

    # Creator (manager) successfully registers summary and minutes_url
    switch_user(client, "mgr_hu46@dashnode.io")
    res_ok = client.post(
        f"/api/v1/availability/meetings/{past_id}/summary",
        json={
            "summary": "Acuerdos del sprint: se definieron los objetivos del release.",
            "minutes_url": "https://docs.google.com/document/d/acta-final-123",
        },
    )
    assert res_ok.status_code == 200
    saved_data = res_ok.json()
    assert saved_data["summary"] == "Acuerdos del sprint: se definieron los objetivos del release."
    assert saved_data["minutes_url"] == "https://docs.google.com/document/d/acta-final-123"
    assert saved_data["status"] == "completed"

    # Participant developer can view summary and minutes URL in detail
    switch_user(client, "dev_hu46@dashnode.io")
    res_view = client.get(f"/api/v1/availability/meetings/{past_id}")
    assert res_view.status_code == 200
    view_data = res_view.json()
    assert view_data["summary"] == "Acuerdos del sprint: se definieron los objetivos del release."
    assert view_data["minutes_url"] == "https://docs.google.com/document/d/acta-final-123"
    assert view_data["status"] == "completed"

    # Admin can also update summary and minutes URL
    switch_user(client, "admin_hu46@dashnode.io")
    res_admin_update = client.post(
        f"/api/v1/availability/meetings/{past_id}/summary",
        json={
            "summary": "Resumen actualizado por administrador.",
            "minutes_url": "https://notion.so/acta-admin",
        },
    )
    assert res_admin_update.status_code == 200
    assert res_admin_update.json()["summary"] == "Resumen actualizado por administrador."
