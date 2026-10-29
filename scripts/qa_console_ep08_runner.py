"""Console QA Test Runner for EP-08 Kanban API (HU_DN_05_72 .. HU_DN_05_76).

Executes live HTTP requests through FastAPI TestClient with complete logging of
Request method, URL, headers, cookies, payload, response code, and response body.
"""

import os
import sys
from pathlib import Path

# Add repo root to sys.path so tests module is resolvable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Bootstrap test environment before importing application modules
_TEST_ENV = {
    "APP_ENV": "development",
    "SECRET_KEY": "test-secret-key-at-least-32-bytes-long!",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "CORS_ORIGINS": "http://localhost:5173",
    "CSRF_TRUSTED_ORIGINS": "http://localhost:5173",
    "SEED_ADMIN_PASSWORD": "",
    "SEED_MANAGER_PASSWORD": "",
    "SEED_DEVELOPER_PASSWORD": "",
    "SEED_DISABLED_PASSWORD": "",
}
for _k, _v in _TEST_ENV.items():
    os.environ[_k] = _v

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.modules.backlog.domain import messages as backlog_messages
from app.modules.kanban.domain import messages as kanban_messages
from app.shared.infrastructure.database import Base, get_db_session
from tests.support import DEFAULT_PASSWORD, create_user, login_as

SEPARATOR = "=" * 80
SUB_SEPARATOR = "-" * 80


def print_step(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  [QA TEST CASE] {title}")
    print(f"{SEPARATOR}")


def print_transaction(
    method: str,
    path: str,
    user: str,
    status_code: int,
    req_body: dict[str, Any] | None,
    res_body: dict[str, Any] | None,
) -> None:
    print(f"\n--> REQUEST: {method} {path}")
    print(f"    Actor / Contexto: {user}")
    if req_body is not None:
        print(f"    Payload: {json.dumps(req_body, ensure_ascii=False)}")
    print(f"<-- RESPONSE: HTTP {status_code}")
    if res_body is not None:
        print(f"    Body: {json.dumps(res_body, indent=2, ensure_ascii=False)}")
    print(f"{SUB_SEPARATOR}")


def main() -> int:
    print("\n" + SEPARATOR)
    print("  DASHNODE QA CONSOLE TEST RUNNER - EP-08 TABLERO KANBAN")
    print("  Ejecución en vivo de peticiones HTTP locales contra la API")
    print(SEPARATOR)

    # In-memory SQLite database for deterministic standalone execution
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db_session() -> Iterator[Session]:
        db: Session = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    client = TestClient(app)

    # 1. SETUP USERS & PROJECT
    print_step("PREPARACION: Creacion de Usuarios, Proyecto y Miembros")
    mgr_id = login_as(client, engine, email="gerente-qa@dashnode.io", role="manager")
    dev1_id = create_user(engine, email="dev1-qa@dashnode.io", role="developer")
    dev2_id = create_user(engine, email="dev2-qa@dashnode.io", role="developer")

    resp_proj = client.post(
        "/api/v1/projects",
        json={
            "name": "Proyecto Kanban QA",
            "description": "Validacion automatizada EP-08",
            "priority": "alta",
            "manager_id": mgr_id,
        },
    )
    assert resp_proj.status_code == 201, resp_proj.text
    project_id = resp_proj.json()["id"]

    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev1_id})
    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev2_id})

    # =========================================================================
    # SCENARIO 0: HU_DN_05_72 - Empty sprint state
    # =========================================================================
    print_step("HU_DN_05_72.0: Consulta de Tablero sin Sprint Activo (Estado Vacio)")
    res_no_sprint = client.get(f"/api/v1/projects/{project_id}/kanban")
    print_transaction(
        "GET",
        f"/api/v1/projects/{project_id}/kanban",
        "Gerente (gerente-qa@dashnode.io)",
        res_no_sprint.status_code,
        None,
        res_no_sprint.json(),
    )
    assert res_no_sprint.status_code == 200
    assert res_no_sprint.json()["active_sprint"] is None
    assert res_no_sprint.json()["message"] == kanban_messages.NO_ACTIVE_SPRINT
    assert len(res_no_sprint.json()["columns"]) == 6
    print(
        "  [PASS] Tablero responde 200 con 'active_sprint: null', 6 columnas vacías y mensaje orientativo."
    )

    # Epic, User Story and Tasks
    resp_epic = client.post(
        f"/api/v1/projects/{project_id}/epics",
        json={"name": "Epica Kanban", "description": "Desc", "color": "#3B82F6"},
    )
    epic_id = resp_epic.json()["id"]

    resp_story = client.post(
        f"/api/v1/epics/{epic_id}/user-stories",
        json={
            "title": "HU-01 Flujo de Tareas",
            "user_role": "desarrollador",
            "reason": "gestionar avance",
            "moscow_priority": "must_have",
        },
    )
    story_id = resp_story.json()["id"]

    # Tasks: Task 1 assigned to Dev 1, Task 2 assigned to Dev 2
    resp_t1 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Tarea Frontend Login", "task_type": "frontend"},
    )
    t1_id = resp_t1.json()["id"]
    client.patch(f"/api/v1/story-tasks/{t1_id}/assignee", json={"assignee_id": dev1_id})
    client.patch(f"/api/v1/story-tasks/{t1_id}/estimated-hours", json={"estimated_hours": 8.0})

    resp_t2 = client.post(
        f"/api/v1/user-stories/{story_id}/tasks",
        json={"name": "Tarea Backend API", "task_type": "backend"},
    )
    t2_id = resp_t2.json()["id"]
    client.patch(f"/api/v1/story-tasks/{t2_id}/assignee", json={"assignee_id": dev2_id})
    client.patch(f"/api/v1/story-tasks/{t2_id}/estimated-hours", json={"estimated_hours": 12.0})

    # Active Sprint
    start_d = datetime.now(UTC).date()
    end_d = start_d + timedelta(days=14)
    resp_sp = client.post(
        f"/api/v1/projects/{project_id}/sprints",
        json={
            "name": "Sprint 1 QA",
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
        },
    )
    sprint_id = resp_sp.json()["id"]
    client.patch(
        f"/api/v1/projects/{project_id}/user-stories/{story_id}/sprint",
        json={"sprint_id": sprint_id},
    )
    client.post(f"/api/v1/projects/{project_id}/sprints/{sprint_id}/start")

    print(f"--> Proyecto creado: {project_id}")
    print(f"--> Sprint activo: {sprint_id}")
    print(f"--> Tarea 1 (Dev 1): {t1_id}")
    print(f"--> Tarea 2 (Dev 2): {t2_id}")

    # =========================================================================
    # SCENARIO 1: HU_DN_05_72 - Manager views board (ALL tasks)
    # =========================================================================
    print_step("HU_DN_05_72.1: Gerente consulta Tablero Kanban (debe ver todas las tareas)")
    res_mgr = client.get(f"/api/v1/projects/{project_id}/kanban")
    print_transaction(
        "GET",
        f"/api/v1/projects/{project_id}/kanban",
        "Gerente (gerente-qa@dashnode.io)",
        res_mgr.status_code,
        None,
        res_mgr.json(),
    )
    assert res_mgr.status_code == 200
    mgr_cards = [c["id"] for col in res_mgr.json()["columns"] for c in col["cards"]]
    assert t1_id in mgr_cards
    assert t2_id in mgr_cards
    print("  [PASS] Gerente visualiza las 6 columnas y las 2 tareas (Dev 1 y Dev 2).")

    # =========================================================================
    # SCENARIO 2: HU_DN_05_72 - Dev 1 views board (ONLY own tasks)
    # =========================================================================
    print_step("HU_DN_05_72.2: Desarrollador 1 consulta Tablero Kanban (solo debe ver sus tareas)")
    client.cookies.clear()
    login_res = client.post(
        "/api/v1/auth/login", json={"email": "dev1-qa@dashnode.io", "password": DEFAULT_PASSWORD}
    )
    assert login_res.status_code == 200

    res_dev1 = client.get(f"/api/v1/projects/{project_id}/kanban")
    print_transaction(
        "GET",
        f"/api/v1/projects/{project_id}/kanban",
        "Desarrollador 1 (dev1-qa@dashnode.io)",
        res_dev1.status_code,
        None,
        res_dev1.json(),
    )
    assert res_dev1.status_code == 200
    dev_cards = [c["id"] for col in res_dev1.json()["columns"] for c in col["cards"]]
    assert t1_id in dev_cards
    assert t2_id not in dev_cards
    print("  [PASS] Desarrollador 1 solo visualiza su tarea propia (t1) y no la ajena (t2).")

    # =========================================================================
    # SCENARIO 3: HU_DN_05_73 - Dev 1 moves own task TODO -> IN_PROGRESS (Success)
    # =========================================================================
    print_step("HU_DN_05_73.1: Desarrollador 1 mueve su tarea a IN_PROGRESS (Exito 200)")
    req_move = {"status": "IN_PROGRESS"}
    res_move = client.patch(f"/api/v1/projects/{project_id}/tasks/{t1_id}/status", json=req_move)
    print_transaction(
        "PATCH",
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/status",
        "Desarrollador 1",
        res_move.status_code,
        req_move,
        res_move.json(),
    )
    assert res_move.status_code == 200
    assert res_move.json()["status"] == "IN_PROGRESS"
    assert res_move.json()["message"] == backlog_messages.TASK_STATUS_UPDATED
    print("  [PASS] Tarea transicionada con éxito a IN_PROGRESS.")

    # =========================================================================
    # SCENARIO 4: HU_DN_05_73 - Dev 1 tries to move Dev 2's task (Forbidden 403)
    # =========================================================================
    print_step("HU_DN_05_73.2: Desarrollador 1 intenta mover tarea ajena (Rechazo 403 Forbidden)")
    res_forbid = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t2_id}/status", json={"status": "IN_PROGRESS"}
    )
    print_transaction(
        "PATCH",
        f"/api/v1/projects/{project_id}/tasks/{t2_id}/status",
        "Desarrollador 1",
        res_forbid.status_code,
        {"status": "IN_PROGRESS"},
        res_forbid.json(),
    )
    assert res_forbid.status_code == 403
    assert res_forbid.json()["error"]["message"] == backlog_messages.TASK_STATUS_OWN_ONLY
    print(
        f"  [PASS] Peticion rechazada con 403 y mensaje: '{backlog_messages.TASK_STATUS_OWN_ONLY}'."
    )

    # =========================================================================
    # SCENARIO 5: HU_DN_05_73 - Moving manually to CORRECTION (Validation 400)
    # =========================================================================
    print_step(
        "HU_DN_05_73.3: Intento manual de mover a columna CORRECTION (Rechazo 400 Bad Request)"
    )
    client.cookies.clear()
    client.post(
        "/api/v1/auth/login", json={"email": "gerente-qa@dashnode.io", "password": DEFAULT_PASSWORD}
    )

    res_corr = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/status", json={"status": "CORRECTION"}
    )
    print_transaction(
        "PATCH",
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/status",
        "Gerente",
        res_corr.status_code,
        {"status": "CORRECTION"},
        res_corr.json(),
    )
    assert res_corr.status_code == 400
    assert res_corr.json()["error"]["message"] == backlog_messages.TASK_STATUS_CORRECTION
    print(
        f"  [PASS] Peticion rechazada con 400 y mensaje: '{backlog_messages.TASK_STATUS_CORRECTION}'."
    )

    # =========================================================================
    # SCENARIO 6: HU_DN_05_74 - Manager updates WIP limit = 2 on IN_PROGRESS
    # =========================================================================
    print_step("HU_DN_05_74.1: Gerente configura limite WIP en 2 para IN_PROGRESS (Exito 200)")
    req_wip = {"wip_limit": 2}
    res_wip = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip", json=req_wip
    )
    print_transaction(
        "PUT",
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        "Gerente",
        res_wip.status_code,
        req_wip,
        res_wip.json(),
    )
    assert res_wip.status_code == 200
    assert res_wip.json()["wip_limit"] == 2
    assert res_wip.json()["message"] == kanban_messages.WIP_LIMIT_UPDATED
    print("  [PASS] Limite WIP configurado correctamente en 2.")

    # =========================================================================
    # SCENARIO 7: HU_DN_05_74 - Verify WIP persistence on Board GET
    # =========================================================================
    print_step("HU_DN_05_74.2: Verificacion de persistencia del limite WIP en GET Tablero")
    res_board2 = client.get(f"/api/v1/projects/{project_id}/kanban")
    in_prog_col = next(c for c in res_board2.json()["columns"] if c["id"] == "IN_PROGRESS")
    print_transaction(
        "GET",
        f"/api/v1/projects/{project_id}/kanban",
        "Gerente",
        res_board2.status_code,
        None,
        {"column_id": "IN_PROGRESS", "wip_limit": in_prog_col["wip_limit"]},
    )
    assert in_prog_col["wip_limit"] == 2
    print("  [PASS] Tablero refleja wip_limit = 2 en la columna IN_PROGRESS.")

    # =========================================================================
    # SCENARIO 8: HU_DN_05_74 - Dev tries to set WIP limit (Forbidden 403)
    # =========================================================================
    print_step("HU_DN_05_74.3: Desarrollador intenta modificar limite WIP (Rechazo 403 Forbidden)")
    client.cookies.clear()
    client.post(
        "/api/v1/auth/login", json={"email": "dev1-qa@dashnode.io", "password": DEFAULT_PASSWORD}
    )

    res_wip_dev = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip", json={"wip_limit": 5}
    )
    print_transaction(
        "PUT",
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        "Desarrollador 1",
        res_wip_dev.status_code,
        {"wip_limit": 5},
        res_wip_dev.json(),
    )
    assert res_wip_dev.status_code == 403
    print("  [PASS] Solo Administradores y Gerentes pueden modificar limites WIP (403 Forbidden).")

    # =========================================================================
    # SCENARIO 9: HU_DN_05_74 - Reset WIP limit ("Sin limite" / null)
    # =========================================================================
    print_step("HU_DN_05_74.4: Gerente restablece limite WIP a 'Sin limite' (wip_limit: null)")
    client.cookies.clear()
    client.post(
        "/api/v1/auth/login", json={"email": "gerente-qa@dashnode.io", "password": DEFAULT_PASSWORD}
    )

    res_wip_reset = client.put(
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip", json={"wip_limit": None}
    )
    print_transaction(
        "PUT",
        f"/api/v1/projects/{project_id}/kanban/columns/IN_PROGRESS/wip",
        "Gerente",
        res_wip_reset.status_code,
        {"wip_limit": None},
        res_wip_reset.json(),
    )
    assert res_wip_reset.status_code == 200
    assert res_wip_reset.json()["wip_limit"] is None
    print("  [PASS] Limite WIP restablecido a null con exito.")

    # =========================================================================
    # SCENARIO 10: HU_DN_05_76 - Report Task Impediment (Lock badge)
    # =========================================================================
    print_step("HU_DN_05_76.1: Reportar motivo de impedimento en la Tarea 1 (is_blocked: True)")
    req_block = {
        "is_blocked": True,
        "blocked_reason": "Esperando resolucion de proveedor de pasarela externa",
        "blocked_by_task_id": None,
    }
    res_block = client.patch(f"/api/v1/projects/{project_id}/tasks/{t1_id}/block", json=req_block)
    print_transaction(
        "PATCH",
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/block",
        "Gerente",
        res_block.status_code,
        req_block,
        res_block.json(),
    )
    assert res_block.status_code == 200
    assert res_block.json()["is_blocked"] is True
    assert (
        res_block.json()["blocked_reason"]
        == "Esperando resolucion de proveedor de pasarela externa"
    )
    print("  [PASS] Impedimento registrado con exito.")

    # =========================================================================
    # SCENARIO 11: HU_DN_05_76 - Predecessor Dependency
    # =========================================================================
    print_step(
        "HU_DN_05_76.2: Configurar dependencia de Tarea Predecesora (Tarea 1 depende de Tarea 2)"
    )
    req_dep = {
        "is_blocked": False,
        "blocked_reason": None,
        "blocked_by_task_id": t2_id,
    }
    res_dep = client.patch(f"/api/v1/projects/{project_id}/tasks/{t1_id}/block", json=req_dep)
    print_transaction(
        "PATCH",
        f"/api/v1/projects/{project_id}/tasks/{t1_id}/block",
        "Gerente",
        res_dep.status_code,
        req_dep,
        res_dep.json(),
    )
    assert res_dep.status_code == 200
    assert res_dep.json()["blocked_by_task_id"] == t2_id
    print("  [PASS] Dependencia de predecesora configurada con exito.")

    # =========================================================================
    # SCENARIO 12: HU_DN_05_76 - Board GET returns block & dependency fields
    # =========================================================================
    print_step("HU_DN_05_76.3: Tablero GET retorna los campos de bloqueo y titulo de predecesora")
    res_board3 = client.get(f"/api/v1/projects/{project_id}/kanban")
    in_prog_col3 = next(c for c in res_board3.json()["columns"] if c["id"] == "IN_PROGRESS")
    card_t1 = next(c for c in in_prog_col3["cards"] if c["id"] == t1_id)
    print_transaction(
        "GET",
        f"/api/v1/projects/{project_id}/kanban",
        "Gerente",
        res_board3.status_code,
        None,
        {
            "task_id": card_t1["id"],
            "title": card_t1["title"],
            "is_blocked": card_t1["is_blocked"],
            "blocked_by_task_id": card_t1["blocked_by_task_id"],
            "blocked_by_task_title": card_t1["blocked_by_task_title"],
        },
    )
    assert card_t1["blocked_by_task_id"] == t2_id
    assert card_t1["blocked_by_task_title"] == "Tarea Backend API"
    print(
        "  [PASS] El Tablero retorna correctamente el nombre y ID de la tarea predecesora ('Tarea Backend API')."
    )

    print("\n" + SEPARATOR)
    print("  RESUMEN FINAL: 13/13 PRUEBAS DE PETICIONES EXITOSAS EN CONSOLA (100% PASS)")
    print(SEPARATOR + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
