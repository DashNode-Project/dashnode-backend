"""Console QA Test Runner for EP-11 Issues and Evidences (HU_DN_07_97 .. HU_DN_07_101).

Automated QA Execution against DashNode Backend API.
Uses Python `requests` library to trigger real HTTP requests against a local Uvicorn server,
exercising routing, middleware, database persistence, authentication, CORS, file parsing, and HMAC signatures.
"""

import contextlib
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import TypedDict

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Setup isolated test environment
DB_FILE = REPO_ROOT / "qa_ep11_test.db"
if DB_FILE.exists():
    with contextlib.suppress(Exception):
        DB_FILE.unlink()

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_FILE.resolve()}"
os.environ["SECRET_KEY"] = "qa-secret-key-at-least-32-bytes-long!"
os.environ["CORS_ORIGINS"] = (
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080"
)
os.environ["SESSION_COOKIE_SECURE"] = "false"

import requests
import uvicorn
from sqlalchemy import create_engine

from app.main import app
from app.modules.fixes.domain import messages
from app.shared.infrastructure.database import Base
from tests.support import DEFAULT_PASSWORD, create_user

SEPARATOR = "=" * 80
SUB_SEPARATOR = "-" * 80


class QaStepResult(TypedDict):
    step: int
    name: str
    hu: str
    passed: bool
    details: str


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def print_step_header(step_num: int, title: str, hu: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  [QA PASO {step_num}] {title} ({hu})")
    print(f"{SEPARATOR}")


def main() -> int:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    print(f"\n{SEPARATOR}")
    print(f"  INICIANDO EJECUCIÓN EXHAUSTIVA DE QA — ÉPICA 11 EN {base_url}")
    print(f"{SEPARATOR}")

    # Setup tables in SQLite
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # Start uvicorn server in a daemon thread
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to become responsive
    max_wait = 10.0
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < max_wait:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                server_ready = True
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)

    if not server_ready:
        print("ERROR: El servidor Uvicorn no inicio en el tiempo esperado.")
        return 1

    session = requests.Session()
    results: list[QaStepResult] = []

    try:
        # Step 0: Seed test users and project
        mgr_email = "mgr-qa-ep11@dashnode.io"
        dev_email = "dev-qa-ep11@dashnode.io"
        mgr_id = create_user(engine, email=mgr_email, role="manager")
        dev_id = create_user(engine, email=dev_email, role="developer")

        # Login as manager
        login_res = session.post(
            f"{base_url}/api/v1/auth/login", json={"email": mgr_email, "password": DEFAULT_PASSWORD}
        )
        assert login_res.status_code == 200, f"Login manager fallo: {login_res.text}"

        # Create project
        proj_res = session.post(
            f"{base_url}/api/v1/projects",
            json={
                "name": "EP-11 QA Project",
                "description": "Issues & Evidences",
                "priority": "alta",
                "manager_id": mgr_id,
            },
        )
        assert proj_res.status_code == 201, f"Project creation fallo: {proj_res.text}"
        project_id = proj_res.json()["id"]

        # Add developer to project members
        add_mem = session.post(
            f"{base_url}/api/v1/projects/{project_id}/members", json={"user_id": dev_id}
        )
        assert add_mem.status_code in (200, 201), f"Add member fallo: {add_mem.text}"

        # Switch session to developer (active member)
        session.cookies.clear()
        session.post(
            f"{base_url}/api/v1/auth/login", json={"email": dev_email, "password": DEFAULT_PASSWORD}
        )

        # --- STEP 1: HU_DN_07_97 Validaciones de Creación de Issue ---
        print_step_header(
            1, "Validaciones de creación de Issue (Campos obligatorios y límites)", "HU_DN_07_97"
        )
        r1_no_title = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            json={"title": "", "severity": "Alta", "type": "Bug"},
        )
        p1_title = r1_no_title.status_code == 400 and messages.TITLE_REQUIRED in r1_no_title.text

        r1_long_title = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            json={"title": "A" * 101, "severity": "Alta", "type": "Bug"},
        )
        p1_long_title = (
            r1_long_title.status_code == 400 and messages.TITLE_TOO_LONG in r1_long_title.text
        )

        r1_long_desc = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            json={
                "title": "Valid Title",
                "description": "D" * 5001,
                "severity": "Alta",
                "type": "Bug",
            },
        )
        p1_long_desc = (
            r1_long_desc.status_code == 400 and messages.DESCRIPTION_TOO_LONG in r1_long_desc.text
        )

        r1_no_sev = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            json={"title": "Valid Title", "severity": "", "type": "Bug"},
        )
        p1_sev = r1_no_sev.status_code == 400 and messages.SEVERITY_REQUIRED in r1_no_sev.text

        r1_no_type = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            json={"title": "Valid Title", "severity": "Media", "type": ""},
        )
        p1_type = r1_no_type.status_code == 400 and messages.TYPE_REQUIRED in r1_no_type.text

        p1 = p1_title and p1_long_title and p1_long_desc and p1_sev and p1_type
        results.append(
            {
                "step": 1,
                "name": "Validaciones de campos obligatorios y límites de Issue",
                "hu": "HU_DN_07_97",
                "passed": p1,
                "details": "Título requerido/max100, descripción max5000, severidad requerida, tipo requerido",
            }
        )

        # --- STEP 2: HU_DN_07_97 Creación Exitosa e Idempotency-Key ---
        print_step_header(
            2, "Creación exitosa de Issue e idempotencia (Idempotency-Key)", "HU_DN_07_97"
        )
        idemp_key = "idemp-qa-ep11-test-key-001"
        r2 = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            headers={"Idempotency-Key": idemp_key},
            json={
                "title": "Error 500 al guardar perfil de usuario",
                "description": "Se dispara una excepción no controlada en el endpoint /profile",
                "severity": "Crítica",
                "type": "Bug",
            },
        )
        assert r2.status_code == 201, f"Creación de issue falló: {r2.text}"
        issue_data = r2.json()["issue"]
        issue_id = issue_data["id"]

        # Reintento con la misma clave de idempotencia
        r2_retry = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            headers={"Idempotency-Key": idemp_key},
            json={
                "title": "Error 500 al guardar perfil de usuario (reintento)",
                "severity": "Crítica",
                "type": "Bug",
            },
        )
        p2_idemp = (
            r2_retry.status_code == 201
            and r2_retry.json()["issue"]["id"] == issue_id
            and r2_retry.json()["issue"]["status"] == "open"
        )
        results.append(
            {
                "step": 2,
                "name": "Creación exitosa con estado OPEN e Idempotency-Key",
                "hu": "HU_DN_07_97",
                "passed": p2_idemp,
                "details": f"Issue creado ID: {issue_id}, idempotencia validada correctamente",
            }
        )

        # --- STEP 3: HU_DN_07_98 Seguridad: Rechazo de Binarios Peligrosos y Límites de Tamaño ---
        print_step_header(
            3,
            "Seguridad de Evidencias: Rechazo de ejecutables, scripts y límites de tamaño",
            "HU_DN_07_98",
        )
        r3_exe = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
            files={
                "file": (
                    "malware.exe",
                    b"MZ\x90\x00\x03\x00\x00\x00fake_binary",
                    "application/octet-stream",
                )
            },
        )
        p3_exe = r3_exe.status_code == 400 and messages.UNSUPPORTED_FORMAT in r3_exe.text

        r3_sh = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
            files={"file": ("hack.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh")},
        )
        p3_sh = r3_sh.status_code == 400 and messages.UNSUPPORTED_FORMAT in r3_sh.text

        r3_large_log = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
            files={"file": ("heavy.log", b"L" * (1024 * 1024 + 100), "text/plain")},
        )
        p3_log_limit = (
            r3_large_log.status_code == 400 and messages.FILE_TOO_LARGE in r3_large_log.text
        )

        r3_large_img = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
            files={
                "file": (
                    "huge.jpg",
                    b"\xff\xd8\xff\xdb" + (b"0" * (5 * 1024 * 1024 + 100)),
                    "image/jpeg",
                )
            },
        )
        p3_img_limit = (
            r3_large_img.status_code == 400 and messages.FILE_TOO_LARGE in r3_large_img.text
        )

        p3 = p3_exe and p3_sh and p3_log_limit and p3_img_limit
        results.append(
            {
                "step": 3,
                "name": "Rechazo de formatos peligrosos y límites de tamaño por tipo",
                "hu": "HU_DN_07_98",
                "passed": p3,
                "details": "Bloqueo exitoso de .exe, .sh, logs >1MB e imágenes >5MB",
            }
        )

        # --- STEP 4: HU_DN_07_98 Adjunto Válido y Detección de Duplicados SHA-256 ---
        print_step_header(
            4, "Adjunto válido de evidencia y detección de duplicados SHA-256", "HU_DN_07_98"
        )
        valid_jpeg_bytes = b"\xff\xd8\xff\xdb\x00\x43\x00\xff\xda\x00\x02\x11\x22\xff\xd9"
        r4_attach = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
            data={"title": "Captura del error 500"},
            files={"file": ("error_screenshot.jpg", valid_jpeg_bytes, "image/jpeg")},
        )
        assert r4_attach.status_code == 201, f"Adjuntar evidencia falló: {r4_attach.text}"
        ev_data = r4_attach.json()["evidence"]
        evidence_id = ev_data["id"]

        r4_dup = session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
            data={"title": "Copia duplicada"},
            files={"file": ("duplicate_screenshot.jpg", valid_jpeg_bytes, "image/jpeg")},
        )
        p4_dup = r4_dup.status_code == 409 and messages.DUPLICATE_EVIDENCE in r4_dup.text

        p4 = r4_attach.status_code == 201 and p4_dup
        results.append(
            {
                "step": 4,
                "name": "Adjunto exitoso y rechazo de duplicados SHA-256 (409)",
                "hu": "HU_DN_07_98",
                "passed": p4,
                "details": f"Evidencia adjuntada ID: {evidence_id}, duplicado rechazado con código 409",
            }
        )

        # --- STEP 5: HU_DN_07_99 Listado de Issues y Paginación por Cursor ---
        print_step_header(
            5, "Listado de issues de un proyecto y ordenamiento por defecto", "HU_DN_07_99"
        )
        session.post(
            f"{base_url}/api/v1/projects/{project_id}/issues",
            json={"title": "Espaciado incorrecto en navbar", "severity": "Baja", "type": "UX"},
        )
        r5_list = session.get(f"{base_url}/api/v1/projects/{project_id}/issues?limit=10")
        assert r5_list.status_code == 200, f"Listado falló: {r5_list.text}"
        list_body = r5_list.json()
        items = list_body["items"]
        total = list_body["total"]

        p5_order = (
            len(items) >= 2 and items[0]["severity"] == "critical" and items[1]["severity"] == "low"
        )

        r5_page1 = session.get(f"{base_url}/api/v1/projects/{project_id}/issues?limit=1")
        next_cursor = r5_page1.json()["next_cursor"]
        r5_page2 = session.get(
            f"{base_url}/api/v1/projects/{project_id}/issues?limit=1&cursor={next_cursor}"
        )
        p5_paging = (
            r5_page1.status_code == 200
            and len(r5_page1.json()["items"]) == 1
            and r5_page2.status_code == 200
            and len(r5_page2.json()["items"]) == 1
            and r5_page1.json()["items"][0]["id"] != r5_page2.json()["items"][0]["id"]
        )

        p5 = p5_order and p5_paging
        results.append(
            {
                "step": 5,
                "name": "Listado con orden (open > severidad > fecha) y paginación por cursor",
                "hu": "HU_DN_07_99",
                "passed": p5,
                "details": f"Total issues: {total}, orden verificado (Crítica -> Baja), cursor paginación OK",
            }
        )

        # --- STEP 6: HU_DN_07_100 Detalle de Issue y URLs Firmadas HMAC (5 min) ---
        print_step_header(
            6,
            "Detalle de Issue y descarga segura mediante URLs firmadas HMAC-SHA256",
            "HU_DN_07_100",
        )
        r6_detail = session.get(f"{base_url}/api/v1/projects/{project_id}/issues/{issue_id}")
        assert r6_detail.status_code == 200, f"Detalle de issue falló: {r6_detail.text}"
        detail_data = r6_detail.json()

        assert len(detail_data["evidences"]) > 0, "No se listaron evidencias en el detalle"
        download_url = detail_data["evidences"][0]["download_url"]

        r6_download = session.get(f"{base_url}{download_url}")
        p6_valid_dl = r6_download.status_code == 200 and r6_download.content == valid_jpeg_bytes

        tampered_url = download_url.replace("signature=", "signature=tampered_signature_")
        r6_tampered = session.get(f"{base_url}{tampered_url}")
        p6_tampered_blocked = (
            r6_tampered.status_code == 403
            and messages.SIGNATURE_INVALID_OR_EXPIRED in r6_tampered.text
        )

        expired_url = download_url.split("&expires=")[0] + "&expires=1000000000"
        r6_expired = session.get(f"{base_url}{expired_url}")
        p6_expired_blocked = r6_expired.status_code == 403

        p6 = p6_valid_dl and p6_tampered_blocked and p6_expired_blocked
        results.append(
            {
                "step": 6,
                "name": "Detalle con evidencias y seguridad de URLs firmadas HMAC (300s)",
                "hu": "HU_DN_07_100",
                "passed": p6,
                "details": "Descarga binaria exitosa; firmas alteradas y expiradas rechazadas con 403 Forbidden",
            }
        )

        # --- STEP 7: HU_DN_07_101 Filtrado de Issues por Estado, Severidad y Tipo ---
        print_step_header(
            7, "Filtrado en servidor por estado, severidad y tipo (AND lógico)", "HU_DN_07_101"
        )
        r7_match = session.get(
            f"{base_url}/api/v1/projects/{project_id}/issues?severity=critical&type=bug"
        )
        p7_match = r7_match.status_code == 200 and len(r7_match.json()["items"]) == 1

        r7_no_match = session.get(
            f"{base_url}/api/v1/projects/{project_id}/issues?severity=critical&type=ux"
        )
        p7_no_match = r7_no_match.status_code == 200 and len(r7_no_match.json()["items"]) == 0

        r7_status = session.get(f"{base_url}/api/v1/projects/{project_id}/issues?status=open")
        p7_status = r7_status.status_code == 200 and len(r7_status.json()["items"]) >= 2

        p7 = p7_match and p7_no_match and p7_status
        results.append(
            {
                "step": 7,
                "name": "Filtrado multinivel con lógica AND en backend",
                "hu": "HU_DN_07_101",
                "passed": p7,
                "details": "Coincidencia exacta, filtros combinados y retorno vacío validados correctamente",
            }
        )

    finally:
        server.should_exit = True
        if DB_FILE.exists():
            with contextlib.suppress(Exception):
                DB_FILE.unlink()

    # Print Summary Table
    print(f"\n{SEPARATOR}")
    print("  RESUMEN DE RESULTADOS QA — ÉPICA 11 (HU_DN_07_97 .. HU_DN_07_101)")
    print(f"{SEPARATOR}")
    all_passed = True
    for res in results:
        status_str = "PASS" if res["passed"] else "FAIL"
        if not res["passed"]:
            all_passed = False
        print(f"[{status_str}] Paso {res['step']}: {res['name']} ({res['hu']})")
        print(f"       Detalle: {res['details']}")

    print(f"{SEPARATOR}")
    if all_passed:
        print(">>> RESULTADO GLOBAL: 100% DE PRUEBAS PASADAS (7/7 CASOS EXITOSOS) <<<")
        print(f"{SEPARATOR}\n")
        return 0
    else:
        print(">>> EXISTIERON FALLOS EN LA EJECUCIÓN DE QA <<<")
        print(f"{SEPARATOR}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
