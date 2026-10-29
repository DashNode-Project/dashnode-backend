"""Console QA Test Runner for EP-09 Documentation API (HU_DN_06_77 .. HU_DN_06_89).

Automated QA Execution against DashNode Backend API.
Uses Python `requests` library to trigger real HTTP requests against the local server.
"""

import contextlib
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Setup isolated environment
DB_FILE = REPO_ROOT / "qa_ep09_test.db"
if DB_FILE.exists():
    DB_FILE.unlink()

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{DB_FILE.resolve()}"
os.environ["SECRET_KEY"] = "qa-secret-key-at-least-32-bytes-long!"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:3000"
os.environ["SESSION_COOKIE_SECURE"] = "false"

import requests
import uvicorn
from sqlalchemy import create_engine

from app.main import app
from app.shared.infrastructure.database import Base
from tests.support import DEFAULT_PASSWORD, create_user

SEPARATOR = "=" * 80
SUB_SEPARATOR = "-" * 80


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def print_step_header(step_num: int, title: str, hu: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  [QA PASO {step_num}] {title} ({hu})")
    print(f"{SEPARATOR}")


def print_transaction(
    method: str,
    url: str,
    actor: str,
    token_preview: str,
    req_body: dict | None,
    res_status: int,
    res_body: dict | list | None,
) -> None:
    print(f"--> REQUEST: {method} {url}")
    print(f"    Actor / Rol: {actor}")
    print(f"    Token: {token_preview}")
    if req_body is not None:
        print(f"    Payload: {json.dumps(req_body, ensure_ascii=False)}")
    print(f"<-- RESPONSE: HTTP {res_status}")
    if res_body is not None:
        print(f"    Body: {json.dumps(res_body, indent=2, ensure_ascii=False)}")
    print(f"{SUB_SEPARATOR}")


def get_token_headers_and_cookies(token: str) -> tuple[dict, dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    cookies = {
        "dashnode_session": token,
    }
    return headers, cookies


def main() -> int:
    print("\n" + SEPARATOR)
    print("  DASHNODE QA AUTOMATION TEST RUNNER - EP-09 DOCUMENTACION Y BASE DE CONOCIMIENTO")
    print("  Ejecución automatizada local con Python 'requests' contra el servidor backend")
    print(SEPARATOR)

    # 1. Setup SQLite database schema
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # 2. Start Uvicorn server on a free local port
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    print(f"\n[INFO] Iniciando servidor backend Uvicorn en {base_url} ...")

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server ready
    ready = False
    for _ in range(50):
        try:
            r = requests.get(f"{base_url}/api/v1/auth/session", timeout=1)
            ready = True
            break
        except Exception:
            time.sleep(0.1)

    if not ready:
        print("[ERROR] No fue posible conectar al servidor backend local.")
        return 1

    print(f"[OK] Servidor backend respondiendo en {base_url}\n")

    # 3. Setup test users and seed credentials
    print(f"{SEPARATOR}")
    print("  PREPARACION DEL ENTORNO (SETUP): Usuarios, Proyecto y Tokens de Sesión")
    print(f"{SEPARATOR}")

    admin_email = "admin-qa@dashnode.io"
    manager_email = "manager-qa@dashnode.io"
    dev1_email = "dev1-author-qa@dashnode.io"
    dev2_email = "dev2-other-qa@dashnode.io"

    create_user(engine, email=admin_email, role="admin", name="Admin QA")
    mgr_id = create_user(engine, email=manager_email, role="manager", name="Manager QA")
    dev1_id = create_user(engine, email=dev1_email, role="developer", name="Dev Author QA")
    dev2_id = create_user(engine, email=dev2_email, role="developer", name="Dev Other QA")

    # Log in each user via real HTTP endpoint to obtain genuine session tokens
    def login_user(email: str) -> str:
        res = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": DEFAULT_PASSWORD},
            timeout=5,
        )
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        token = res.cookies.get("dashnode_session")
        if not token:
            # Fallback to response json if token provided
            token = res.json().get("token") or res.json().get("session_token")
        return token

    TOKEN_ADMIN = login_user(admin_email)  # noqa: N806
    TOKEN_MANAGER = login_user(manager_email)  # noqa: N806
    TOKEN_DEV = login_user(dev1_email)  # noqa: N806
    TOKEN_DEV2 = login_user(dev2_email)  # noqa: N806

    print(f"  TOKEN_ADMIN   : {TOKEN_ADMIN[:12]}... (Admin: {admin_email})")
    print(f"  TOKEN_MANAGER : {TOKEN_MANAGER[:12]}... (Gerente: {manager_email})")
    print(f"  TOKEN_DEV     : {TOKEN_DEV[:12]}... (Desarrollador Autor: {dev1_email})")
    print(f"  TOKEN_DEV2    : {TOKEN_DEV2[:12]}... (Otro Desarrollador: {dev2_email})")

    # Create project as manager and add dev1 and dev2 as members
    headers_mgr, cookies_mgr = get_token_headers_and_cookies(TOKEN_MANAGER)
    res_proj = requests.post(
        f"{base_url}/api/v1/projects",
        json={
            "name": "Proyecto QA Documentación EP-09",
            "description": "Validación automatizada de Historias de Usuario EP-09",
            "priority": "alta",
            "manager_id": mgr_id,
        },
        headers=headers_mgr,
        cookies=cookies_mgr,
        timeout=5,
    )
    assert res_proj.status_code == 201, f"Failed to create project: {res_proj.text}"
    PROJECT_ID = res_proj.json()["id"]  # noqa: N806
    print(f"  PROJECT_ID    : {PROJECT_ID}")

    # Add dev1 and dev2 as members
    requests.post(
        f"{base_url}/api/v1/projects/{PROJECT_ID}/members",
        json={"user_id": dev1_id},
        headers=headers_mgr,
        cookies=cookies_mgr,
        timeout=5,
    )
    requests.post(
        f"{base_url}/api/v1/projects/{PROJECT_ID}/members",
        json={"user_id": dev2_id},
        headers=headers_mgr,
        cookies=cookies_mgr,
        timeout=5,
    )
    print("  Miembros vinculados al proyecto: Manager, Dev1 (autor), Dev2 (otro)")

    results: list[dict] = []
    entry_id = None

    # =========================================================================
    # ESCENARIO 1: Ciclo de vida de creación, rechazo y reenvío (HU 77, 85, 86)
    # =========================================================================

    # --- PASO 1 ---
    print_step_header(1, "Crear entrada de documentación", "HU_DN_06_77")
    p1_payload = {
        "title": "Guía de API",
        "category": "TECH",
        "content": "Detalles...",
        "external_url": "https://example.com",
    }
    h_dev, c_dev = get_token_headers_and_cookies(TOKEN_DEV)
    p1_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation"
    r1 = requests.post(p1_url, json=p1_payload, headers=h_dev, cookies=c_dev, timeout=5)
    r1_body = (
        r1.json() if r1.headers.get("content-type", "").startswith("application/json") else r1.text
    )
    print_transaction(
        "POST",
        p1_url,
        f"Desarrollador Autor ({dev1_email})",
        f"{TOKEN_DEV[:10]}...",
        p1_payload,
        r1.status_code,
        r1_body,
    )

    entry_data = r1_body.get("entry", {}) if isinstance(r1_body, dict) else {}
    entry_id = entry_data.get("id") or (r1_body.get("id") if isinstance(r1_body, dict) else None)
    entry_status = (
        entry_data.get("status")
        or entry_data.get("approval_status")
        or (r1_body.get("status") if isinstance(r1_body, dict) else None)
    )

    p1_pass = (r1.status_code == 201) and (entry_id is not None) and (entry_status == "PENDING")
    p1_msg = f"Status 201, entryId={entry_id}, status='{entry_status}'"
    print(f"    ASSERT: {'✅ PASÓ' if p1_pass else '❌ FALLÓ'} -> {p1_msg}")
    results.append(
        {
            "step": 1,
            "name": "Crear entrada (POST)",
            "hu": "HU_DN_06_77",
            "passed": p1_pass,
            "details": p1_msg,
        }
    )

    # --- PASO 2 ---
    print_step_header(2, "Rechazar entrada pendiente con motivo", "HU_DN_06_85")
    p2_payload = {"rejection_reason": "Falta detalle"}
    p2_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}/reject"
    r2 = requests.post(p2_url, json=p2_payload, headers=headers_mgr, cookies=cookies_mgr, timeout=5)
    r2_body = (
        r2.json() if r2.headers.get("content-type", "").startswith("application/json") else r2.text
    )
    print_transaction(
        "POST",
        p2_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        p2_payload,
        r2.status_code,
        r2_body,
    )

    p2_pass = r2.status_code == 200
    p2_msg = f"Status {r2.status_code} (esperado 200)"
    print(f"    ASSERT: {'✅ PASÓ' if p2_pass else '❌ FALLÓ'} -> {p2_msg}")
    results.append(
        {
            "step": 2,
            "name": "Rechazar entrada (POST)",
            "hu": "HU_DN_06_85",
            "passed": p2_pass,
            "details": p2_msg,
        }
    )

    # --- PASO 3 ---
    print_step_header(3, "Reenviar entrada rechazada a nueva revisión", "HU_DN_06_86")
    p3_payload = {"title": "Guía de API v2", "content": "Detalles actualizados..."}
    p3_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}/resubmit"
    r3 = requests.post(p3_url, json=p3_payload, headers=h_dev, cookies=c_dev, timeout=5)
    r3_body = (
        r3.json() if r3.headers.get("content-type", "").startswith("application/json") else r3.text
    )
    print_transaction(
        "POST",
        p3_url,
        f"Desarrollador Autor ({dev1_email})",
        f"{TOKEN_DEV[:10]}...",
        p3_payload,
        r3.status_code,
        r3_body,
    )

    e3_data = r3_body.get("entry", {}) if isinstance(r3_body, dict) else {}
    e3_status = (
        e3_data.get("status")
        or e3_data.get("approval_status")
        or (r3_body.get("status") if isinstance(r3_body, dict) else None)
    )

    p3_pass = (r3.status_code == 200) and (e3_status == "PENDING")
    p3_msg = f"Status 200, status='{e3_status}'"
    print(f"    ASSERT: {'✅ PASÓ' if p3_pass else '❌ FALLÓ'} -> {p3_msg}")
    results.append(
        {
            "step": 3,
            "name": "Reenviar entrada (POST)",
            "hu": "HU_DN_06_86",
            "passed": p3_pass,
            "details": p3_msg,
        }
    )

    # =========================================================================
    # ESCENARIO 2: Aprobación y visibilidad (HU 83, 84, 82)
    # =========================================================================

    # --- PASO 4 ---
    print_step_header(4, "Consultar cola de entradas pendientes", "HU_DN_06_83")
    p4_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/pending"
    r4 = requests.get(p4_url, headers=headers_mgr, cookies=cookies_mgr, timeout=5)
    r4_body = (
        r4.json() if r4.headers.get("content-type", "").startswith("application/json") else r4.text
    )
    print_transaction(
        "GET",
        p4_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        None,
        r4.status_code,
        r4_body,
    )

    pending_list = []
    if isinstance(r4_body, dict):
        pending_list = r4_body.get("pending_entries") or r4_body.get("entries") or []
    contains_entry = any(item.get("id") == entry_id for item in pending_list)

    p4_pass = (r4.status_code == 200) and contains_entry
    p4_msg = f"Status 200, pending_entries contiene entryId={entry_id}"
    print(f"    ASSERT: {'✅ PASÓ' if p4_pass else '❌ FALLÓ'} -> {p4_msg}")
    results.append(
        {
            "step": 4,
            "name": "Consultar cola de pendientes (GET)",
            "hu": "HU_DN_06_83",
            "passed": p4_pass,
            "details": p4_msg,
        }
    )

    # --- PASO 5 ---
    print_step_header(5, "Aprobar entrada de documentación", "HU_DN_06_84")
    p5_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}/approve"
    r5 = requests.post(p5_url, headers=headers_mgr, cookies=cookies_mgr, timeout=5)
    r5_body = (
        r5.json() if r5.headers.get("content-type", "").startswith("application/json") else r5.text
    )
    print_transaction(
        "POST",
        p5_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        None,
        r5.status_code,
        r5_body,
    )

    e5_data = r5_body.get("entry", {}) if isinstance(r5_body, dict) else {}
    e5_status = (
        e5_data.get("status")
        or e5_data.get("approval_status")
        or (r5_body.get("status") if isinstance(r5_body, dict) else None)
    )

    p5_pass = (r5.status_code == 200) and (e5_status == "APPROVED")
    p5_msg = f"Status 200, status='{e5_status}'"
    print(f"    ASSERT: {'✅ PASÓ' if p5_pass else '❌ FALLÓ'} -> {p5_msg}")
    results.append(
        {
            "step": 5,
            "name": "Aprobar entrada (POST)",
            "hu": "HU_DN_06_84",
            "passed": p5_pass,
            "details": p5_msg,
        }
    )

    # --- PASO 6 ---
    print_step_header(6, "Cambiar visibilidad para desarrolladores", "HU_DN_06_82")
    p6_payload = {"is_visible_to_devs": False}
    p6_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}/visibility"
    r6 = requests.patch(
        p6_url, json=p6_payload, headers=headers_mgr, cookies=cookies_mgr, timeout=5
    )
    r6_body = (
        r6.json() if r6.headers.get("content-type", "").startswith("application/json") else r6.text
    )
    print_transaction(
        "PATCH",
        p6_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        p6_payload,
        r6.status_code,
        r6_body,
    )

    e6_data = r6_body.get("entry", {}) if isinstance(r6_body, dict) else {}
    e6_vis = (
        e6_data.get("is_visible_to_devs")
        if "is_visible_to_devs" in e6_data
        else (r6_body.get("is_visible_to_devs") if isinstance(r6_body, dict) else None)
    )

    p6_pass = (r6.status_code == 200) and (e6_vis is False)
    p6_msg = f"Status 200, is_visible_to_devs={e6_vis}"
    print(f"    ASSERT: {'✅ PASÓ' if p6_pass else '❌ FALLÓ'} -> {p6_msg}")
    results.append(
        {
            "step": 6,
            "name": "Cambiar visibilidad (PATCH)",
            "hu": "HU_DN_06_82",
            "passed": p6_pass,
            "details": p6_msg,
        }
    )

    # =========================================================================
    # ESCENARIO 3: Consulta, Anclaje y Eliminación (HU 80, 81, 87/89, 79)
    # =========================================================================

    # --- PASO 7 ---
    print_step_header(7, "Acceso denegado a entrada restringida", "HU_DN_06_81")
    h_dev2, c_dev2 = get_token_headers_and_cookies(TOKEN_DEV2)
    p7_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}"
    r7 = requests.get(p7_url, headers=h_dev2, cookies=c_dev2, timeout=5)
    r7_body = (
        r7.json() if r7.headers.get("content-type", "").startswith("application/json") else r7.text
    )
    print_transaction(
        "GET",
        p7_url,
        f"Otro Desarrollador ({dev2_email})",
        f"{TOKEN_DEV2[:10]}...",
        None,
        r7.status_code,
        r7_body,
    )

    p7_pass = r7.status_code == 403
    p7_msg = "Status 403 Forbidden (esperado 403)"
    print(f"    ASSERT: {'✅ PASÓ' if p7_pass else '❌ FALLÓ'} -> {p7_msg}")
    results.append(
        {
            "step": 7,
            "name": "Acceso denegado (GET)",
            "hu": "HU_DN_06_81",
            "passed": p7_pass,
            "details": p7_msg,
        }
    )

    # --- PASO 8 ---
    print_step_header(8, "Anclar entrada de documentación destacada", "HU_DN_06_87 / 89")
    p8_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}/pin"
    p8_payload = {"is_pinned": True}
    r8 = requests.patch(
        p8_url, json=p8_payload, headers=headers_mgr, cookies=cookies_mgr, timeout=5
    )
    r8_body = (
        r8.json() if r8.headers.get("content-type", "").startswith("application/json") else r8.text
    )
    print_transaction(
        "PATCH",
        p8_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        p8_payload,
        r8.status_code,
        r8_body,
    )

    e8_data = r8_body.get("entry", {}) if isinstance(r8_body, dict) else {}
    e8_pin = (
        e8_data.get("is_pinned")
        if "is_pinned" in e8_data
        else (r8_body.get("is_pinned") if isinstance(r8_body, dict) else None)
    )

    p8_pass = (r8.status_code == 200) and (e8_pin is True)
    p8_msg = f"Status 200, is_pinned={e8_pin}"
    print(f"    ASSERT: {'✅ PASÓ' if p8_pass else '❌ FALLÓ'} -> {p8_msg}")
    results.append(
        {
            "step": 8,
            "name": "Anclar entrada (PATCH)",
            "hu": "HU_DN_06_87 / 89",
            "passed": p8_pass,
            "details": p8_msg,
        }
    )

    # --- PASO 9 ---
    print_step_header(9, "Consultar catálogo de proyecto con entradas ancladas", "HU_DN_06_80")
    p9_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation"
    r9 = requests.get(p9_url, headers=headers_mgr, cookies=cookies_mgr, timeout=5)
    r9_body = (
        r9.json() if r9.headers.get("content-type", "").startswith("application/json") else r9.text
    )
    print_transaction(
        "GET",
        p9_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        None,
        r9.status_code,
        r9_body,
    )

    catalog_entries = r9_body.get("entries", []) if isinstance(r9_body, dict) else []
    target_item = next((item for item in catalog_entries if item.get("id") == entry_id), None)
    is_item_pinned = bool(target_item and target_item.get("is_pinned") is True)

    p9_pass = (r9.status_code == 200) and (target_item is not None) and is_item_pinned
    p9_msg = f"Status 200, entryId={entry_id} en catálogo con is_pinned={is_item_pinned}"
    print(f"    ASSERT: {'✅ PASÓ' if p9_pass else '❌ FALLÓ'} -> {p9_msg}")
    results.append(
        {
            "step": 9,
            "name": "Consultar catálogo (GET)",
            "hu": "HU_DN_06_80",
            "passed": p9_pass,
            "details": p9_msg,
        }
    )

    # --- PASO 10 ---
    print_step_header(10, "Eliminar entrada de documentación (Borrado lógico)", "HU_DN_06_79")
    h_adm, c_adm = get_token_headers_and_cookies(TOKEN_ADMIN)
    p10_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}"
    r10 = requests.delete(p10_url, headers=h_adm, cookies=c_adm, timeout=5)
    r10_body = (
        r10.json()
        if r10.headers.get("content-type", "").startswith("application/json")
        else r10.text
    )
    print_transaction(
        "DELETE",
        p10_url,
        f"Administrador ({admin_email})",
        f"{TOKEN_ADMIN[:10]}...",
        None,
        r10.status_code,
        r10_body,
    )

    p10_pass = r10.status_code == 200
    p10_msg = f"Status {r10.status_code} (esperado 200)"
    print(f"    ASSERT: {'✅ PASÓ' if p10_pass else '❌ FALLÓ'} -> {p10_msg}")
    results.append(
        {
            "step": 10,
            "name": "Eliminar entrada (DELETE)",
            "hu": "HU_DN_06_79",
            "passed": p10_pass,
            "details": p10_msg,
        }
    )

    # --- PASO 11 ---
    print_step_header(11, "Verificar borrado lógico de entrada", "HU_DN_06_79")
    p11_url = f"{base_url}/api/v1/projects/{PROJECT_ID}/documentation/{entry_id}"
    r11 = requests.get(p11_url, headers=headers_mgr, cookies=cookies_mgr, timeout=5)
    r11_body = (
        r11.json()
        if r11.headers.get("content-type", "").startswith("application/json")
        else r11.text
    )
    print_transaction(
        "GET",
        p11_url,
        f"Gerente ({manager_email})",
        f"{TOKEN_MANAGER[:10]}...",
        None,
        r11.status_code,
        r11_body,
    )

    p11_pass = r11.status_code in (404, 403)
    p11_msg = f"Status {r11.status_code} (esperado 404 o 403)"
    print(f"    ASSERT: {'✅ PASÓ' if p11_pass else '❌ FALLÓ'} -> {p11_msg}")
    results.append(
        {
            "step": 11,
            "name": "Verificar borrado lógico (GET)",
            "hu": "HU_DN_06_79",
            "passed": p11_pass,
            "details": p11_msg,
        }
    )

    # =========================================================================
    # REPORTE FINAL DE QA AUTOMATIZADO
    # =========================================================================
    print(f"\n{SEPARATOR}")
    print("  REPORTE FINAL DE QA AUTOMATIZADO - ÉPICA 09 (DOCUMENTACIÓN)")
    print(f"{SEPARATOR}")
    print(
        f"{'Paso':<6} | {'Historia de Usuario':<18} | {'Operación / Endpoint':<35} | {'Resultado':<10} | {'Detalles'}"
    )
    print("-" * 115)

    passed_count = 0
    for r in results:
        status_icon = "✅ PASÓ" if r["passed"] else "❌ FALLÓ"
        if r["passed"]:
            passed_count += 1
        print(
            f"{r['step']:<6} | {r['hu']:<18} | {r['name']:<35} | {status_icon:<10} | {r['details']}"
        )

    print("-" * 115)
    print(
        f"TOTAL: {len(results)} ejecutados | {passed_count} PASARON | {len(results) - passed_count} FALLARON"
    )
    print(
        f"ESTADO GENERAL: {'TODOS LOS TESTS PASARON EXITOSAMENTE (100%)' if passed_count == len(results) else 'FALLOS DETECTADOS'}"
    )
    print(SEPARATOR + "\n")

    # Cleanup test db
    if DB_FILE.exists():
        with contextlib.suppress(Exception):
            DB_FILE.unlink()

    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
