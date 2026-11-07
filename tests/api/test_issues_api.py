"""API integration tests for EP-11 Issues and Evidences (HU_DN_07_97 .. HU_DN_07_101).

@sad AD-07, AD-08, AD-10
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

import struct
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.fixes.domain import messages
from app.modules.notifications.infrastructure.models import NotificationModel
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
    mgr_id = login_as(client, db_engine, email="mgr-issues@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1-issues@dashnode.io", role="developer")
    dev2_id = create_user(db_engine, email="dev2-issues@dashnode.io", role="developer")

    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Issues Project",
            "description": "EP-11 Issues & Evidences",
            "priority": "alta",
            "manager_id": mgr_id,
        },
    )
    assert resp.status_code == 201
    project_id = str(resp.json()["id"])

    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev1_id})
    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev2_id})

    return project_id, mgr_id, dev1_id, dev2_id


def test_hu_97_create_issue_success_and_validations(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, mgr_id, dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-issues@dashnode.io")

    # 1. Validation: Title is required
    res_no_title = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "",
            "description": "Error al cargar",
            "severity": "Alta",
            "type": "Bug",
        },
    )
    assert res_no_title.status_code == 400
    assert messages.TITLE_REQUIRED in res_no_title.text

    # 2. Validation: Title too long (>100 chars)
    res_long_title = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "A" * 101,
            "description": "Error",
            "severity": "Alta",
            "type": "Bug",
        },
    )
    assert res_long_title.status_code == 400

    # 3. Validation: Description too long (>5000 chars)
    res_long_desc = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Fix válido",
            "description": "B" * 5001,
            "severity": "Media",
            "type": "Regresión",
        },
    )
    assert res_long_desc.status_code == 400
    assert messages.DESCRIPTION_TOO_LONG in res_long_desc.text

    # 4. Validation: Severity missing or invalid
    res_no_sev = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Fix válido",
            "description": "Detalle",
            "severity": "Invalida",
            "type": "Bug",
        },
    )
    assert res_no_sev.status_code == 400
    assert messages.SEVERITY_REQUIRED in res_no_sev.text

    # 5. Validation: Type missing or invalid
    res_no_type = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Fix válido",
            "description": "Detalle",
            "severity": "Baja",
            "type": "Desconocido",
        },
    )
    assert res_no_type.status_code == 400
    assert messages.TYPE_REQUIRED in res_no_type.text

    # 6. Restriction: Non-member cannot create issue
    outsider_id = create_user(db_engine, email="outsider-issues@dashnode.io", role="developer")
    _switch_user(client, "outsider-issues@dashnode.io")
    res_outsider = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Fix intruso",
            "description": "No debe permitirse",
            "severity": "Baja",
            "type": "Bug",
        },
    )
    assert res_outsider.status_code == 403
    assert messages.NOT_MEMBER_ERROR in res_outsider.text

    # 7. Happy path: Member creates issue with Idempotency-Key
    _switch_user(client, "dev1-issues@dashnode.io")
    idempotency_key = "idemp-hu97-test-key-001"
    res_created = client.post(
        f"/api/v1/projects/{project_id}/issues",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "title": "Fallo en render de tabla",
            "description": "La tabla no muestra las columnas esperadas",
            "severity": "Crítica",
            "type": "Bug",
        },
    )
    assert res_created.status_code == 201
    data = res_created.json()
    assert data["message"] == messages.ISSUE_CREATED
    issue = data["issue"]
    assert issue["title"] == "Fallo en render de tabla"
    assert issue["status"] == "open"
    assert issue["severity"] == "critical"
    assert issue["type"] == "bug"
    created_id = issue["id"]

    # 8. Idempotency test: Retry with same key returns identical issue
    res_retry = client.post(
        f"/api/v1/projects/{project_id}/issues",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "title": "Fallo en render de tabla (reintento)",
            "description": "Reintento de creación",
            "severity": "Crítica",
            "type": "Bug",
        },
    )
    assert res_retry.status_code == 201
    retry_data = res_retry.json()
    assert retry_data["issue"]["id"] == created_id
    assert retry_data["issue"]["title"] == "Fallo en render de tabla"

    # 9. Verify notification event was enqueued
    with Session(db_engine) as session:
        notifs = session.scalars(
            select(NotificationModel).where(NotificationModel.recipient_id == mgr_id)
        ).all()
        assert len(notifs) >= 1
        assert any("Fallo en render de tabla" in n.message for n in notifs)


def test_hu_98_attach_evidence_success_and_security(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-issues@dashnode.io")

    # Create issue
    res_iss = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Problema con render de video",
            "description": "Adjuntar evidencia",
            "severity": "Alta",
            "type": "Rendimiento",
        },
    )
    assert res_iss.status_code == 201
    issue_id = res_iss.json()["issue"]["id"]

    # 1. Reject polyglot executable
    res_poly = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        files={"file": ("virus.exe", b"MZ\x90\x00malicious", "application/octet-stream")},
    )
    assert res_poly.status_code == 400
    assert messages.UNSUPPORTED_FORMAT in res_poly.text

    # 2. Reject image exceeding 5MB
    large_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * (5 * 1024 * 1024 + 100)
    res_large = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        files={"file": ("large.jpg", large_jpg, "image/jpeg")},
    )
    assert res_large.status_code == 400
    assert messages.FILE_TOO_LARGE in res_large.text

    # 3. Reject video exceeding 60s
    timescale = 1000
    duration = 75000  # 75s > 60s
    mvhd_payload = b"\x00" * 12 + struct.pack(">I", timescale) + struct.pack(">I", duration) + b"\x00" * 40
    mvhd_box = struct.pack(">I", len(mvhd_payload) + 8) + b"mvhd" + mvhd_payload
    moov_box = struct.pack(">I", len(mvhd_box) + 8) + b"moov" + mvhd_box
    ftyp_box = struct.pack(">I", 16) + b"ftypisom\x00\x00\x02\x00"
    too_long_mp4 = ftyp_box + moov_box

    res_long_vid = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        files={"file": ("long.mp4", too_long_mp4, "video/mp4")},
    )
    assert res_long_vid.status_code == 400
    assert messages.VIDEO_TOO_LONG in res_long_vid.text

    # 4. Attach valid JPEG image (with EXIF to verify sanitization)
    app1 = b"\xff\xe1" + struct.pack(">H", 12) + b"Exif\x00\x00Camera1"
    valid_jpeg = b"\xff\xd8\xff" + app1 + b"\xff\xda\x00\x02\xaa\xbb\xff\xd9"
    res_ok = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        data={"title": "Captura del error"},
        files={"file": ("screenshot.jpg", valid_jpeg, "image/jpeg")},
    )
    assert res_ok.status_code == 201
    data_ev = res_ok.json()
    assert data_ev["message"] == messages.EVIDENCE_ATTACHED
    ev = data_ev["evidence"]
    assert ev["title"] == "Captura del error"
    assert ev["file_type"] == "image"
    assert ev["mime_type"] == "image/jpeg"
    assert "signature=" in ev["download_url"]

    # 5. Reject duplicate evidence upload (same SHA-256)
    res_dup = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        data={"title": "Misma captura"},
        files={"file": ("screenshot_copy.jpg", valid_jpeg, "image/jpeg")},
    )
    assert res_dup.status_code == 409
    assert messages.DUPLICATE_EVIDENCE in res_dup.text

    # 6. Attach valid log file
    log_content = b"2026-11-07 [ERROR] Out of bounds exception at line 42\nTraceback complete.\n"
    res_log = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        data={"title": "Log de la consola"},
        files={"file": ("app.log", log_content, "text/plain")},
    )
    assert res_log.status_code == 201
    assert res_log.json()["evidence"]["file_type"] == "log"


def test_hu_99_list_issues_sorting_and_pagination(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-issues@dashnode.io")

    # Initially empty
    res_empty = client.get(f"/api/v1/projects/{project_id}/issues")
    assert res_empty.status_code == 200
    assert res_empty.json()["items"] == []
    assert res_empty.json()["total"] == 0

    # Create several issues with varying severity and status
    client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "Issue Low", "severity": "Baja", "type": "UX"},
    )
    client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "Issue Critical", "severity": "Crítica", "type": "Seguridad"},
    )
    client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "Issue High", "severity": "Alta", "type": "Bug"},
    )

    res_list = client.get(f"/api/v1/projects/{project_id}/issues?limit=25")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) == 3
    # Default ordering: critical comes before high, high before low
    assert items[0]["title"] == "Issue Critical"
    assert items[1]["title"] == "Issue High"
    assert items[2]["title"] == "Issue Low"

    # Test pagination cursor with limit=2
    res_page1 = client.get(f"/api/v1/projects/{project_id}/issues?limit=2")
    assert res_page1.status_code == 200
    page1_data = res_page1.json()
    assert len(page1_data["items"]) == 2
    assert page1_data["next_cursor"] is not None

    res_page2 = client.get(f"/api/v1/projects/{project_id}/issues?limit=2&cursor={page1_data['next_cursor']}")
    assert res_page2.status_code == 200
    page2_data = res_page2.json()
    assert len(page2_data["items"]) == 1
    assert page2_data["items"][0]["title"] == "Issue Low"


def test_hu_100_issue_detail_and_signed_url_security(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-issues@dashnode.io")

    # Create issue & attach evidence
    res_iss = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Detalle completo con firmas",
            "description": "Validar URLs firmadas y vencimiento",
            "severity": "Media",
            "type": "Bug",
        },
    )
    issue_id = res_iss.json()["issue"]["id"]

    valid_jpeg = b"\xff\xd8\xff\xdb\x00\x43\x00\xff\xda\x00\x02\x11\x22\xff\xd9"
    res_ev = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        files={"file": ("shot.jpg", valid_jpeg, "image/jpeg")},
    )
    evidence_id = res_ev.json()["evidence"]["id"]

    # 1. Fetch issue detail
    res_detail = client.get(f"/api/v1/projects/{project_id}/issues/{issue_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["title"] == "Detalle completo con firmas"
    assert len(detail["evidences"]) == 1
    ev_detail = detail["evidences"][0]
    download_url = ev_detail["download_url"]
    assert "signature=" in download_url
    assert "expires=" in download_url

    # 2. Download evidence using signed URL
    res_download = client.get(download_url)
    assert res_download.status_code == 200
    assert res_download.headers["Content-Type"] == "image/jpeg"
    assert res_download.content == valid_jpeg

    # 3. Tampered signature is rejected
    tampered_url = download_url.replace("signature=", "signature=badfake")
    res_tampered = client.get(tampered_url)
    assert res_tampered.status_code == 403
    assert messages.SIGNATURE_INVALID_OR_EXPIRED in res_tampered.text

    # 4. Expired timestamp is rejected
    expired_url = download_url.replace("expires=", "expires=1000000000")
    res_expired = client.get(expired_url)
    assert res_expired.status_code == 403

    # 5. Non-existent issue returns 404
    res_404 = client.get(f"/api/v1/projects/{project_id}/issues/non-existent-issue-id")
    assert res_404.status_code == 404


def test_hu_101_filter_issues_by_status_severity_type(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-issues@dashnode.io")

    client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "Bug Crítico", "severity": "Crítica", "type": "Bug"},
    )
    client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "Seguridad Alta", "severity": "Alta", "type": "Seguridad"},
    )
    client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "UX Baja", "severity": "Baja", "type": "UX"},
    )

    # Filter by severity: Crítica
    res_crit = client.get(f"/api/v1/projects/{project_id}/issues?severity=critical")
    assert res_crit.status_code == 200
    assert len(res_crit.json()["items"]) == 1
    assert res_crit.json()["items"][0]["title"] == "Bug Crítico"

    # Filter by type: Seguridad
    res_sec = client.get(f"/api/v1/projects/{project_id}/issues?type=security")
    assert res_sec.status_code == 200
    assert len(res_sec.json()["items"]) == 1
    assert res_sec.json()["items"][0]["title"] == "Seguridad Alta"

    # Combined filter (AND): type=Bug AND severity=Alta -> No matches
    res_none = client.get(f"/api/v1/projects/{project_id}/issues?type=bug&severity=high")
    assert res_none.status_code == 200
    assert len(res_none.json()["items"]) == 0
    assert res_none.json()["total"] == 0
