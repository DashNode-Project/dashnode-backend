"""API tests for Documentation and Knowledge Base (HU_DN_06_77 .. HU_DN_06_81)."""

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.documentation.domain import messages
from app.modules.documentation.infrastructure.models import DocumentationEntryModel
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
    mgr_id = login_as(client, db_engine, email="mgr-doc@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1-doc@dashnode.io", role="developer")
    dev2_id = create_user(db_engine, email="dev2-doc@dashnode.io", role="developer")

    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Documentation Project",
            "description": "EP-09",
            "priority": "alta",
            "manager_id": mgr_id,
        },
    )
    assert resp.status_code == 201
    project_id = str(resp.json()["id"])

    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev1_id})
    client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": dev2_id})

    return project_id, mgr_id, dev1_id, dev2_id


def test_hu_77_create_documentation_entry_success_and_validations(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-doc@dashnode.io")

    # 1. Validation: Title is required
    res_no_title = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "",
            "category": "Técnica",
            "content": "Contenido válido",
        },
    )
    assert res_no_title.status_code == 400
    assert messages.TITLE_REQUIRED in res_no_title.text

    # 2. Validation: Category is required
    res_no_cat = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Guía de despliegue",
            "category": "Invalida",
            "content": "Contenido válido",
        },
    )
    assert res_no_cat.status_code == 400
    assert messages.CATEGORY_REQUIRED in res_no_cat.text

    # 3. Validation: Missing both content and external_url
    res_no_body = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Guía vacía",
            "category": "Funcional",
            "content": "",
            "external_url": "",
        },
    )
    assert res_no_body.status_code == 400
    assert res_no_body.json()["error"]["message"] == messages.CONTENT_OR_URL_REQUIRED

    # 4. Validation: Invalid URL format
    res_bad_url = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Guía con enlace erróneo",
            "category": "General",
            "external_url": "ftp://bad-url",
        },
    )
    assert res_bad_url.status_code == 400
    assert messages.INVALID_URL in res_bad_url.text

    # 5. Success: Register with text and valid URL
    payload = {
        "title": "Guía de integración con Backend",
        "category": "Técnica",
        "objective": "Documentar contratos de endpoints",
        "tags": "fastapi, jwt, docs",
        "content": "Pasos detallados para consumir los endpoints REST",
        "external_url": "https://api.dashnode.io/docs",
    }
    res_success = client.post(f"/api/v1/projects/{project_id}/documentation", json=payload)
    assert res_success.status_code == 201
    data = res_success.json()
    assert data["message"] == messages.ENTRY_CREATED
    assert data["entry"]["title"] == payload["title"]
    assert data["entry"]["category"] == "Técnica"
    assert data["entry"]["approval_status"] == "PENDING"
    assert data["entry"]["author_id"] == dev1_id


def test_hu_78_update_documentation_entry_and_permissions(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, _dev1_id, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-doc@dashnode.io")

    # Create entry as dev1
    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Documento Inicial",
            "category": "Prompt",
            "content": "Prompt original",
        },
    )
    assert res_c.status_code == 201
    entry_id = res_c.json()["entry"]["id"]

    # 1. Dev1 updates their own PENDING entry
    res_u = client.put(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}",
        json={
            "title": "Documento Modificado",
            "category": "Prompt",
            "content": "Prompt actualizado y mejorado",
        },
    )
    assert res_u.status_code == 200
    assert res_u.json()["message"] == messages.ENTRY_UPDATED
    assert res_u.json()["entry"]["title"] == "Documento Modificado"

    # 2. Dev2 attempts to edit dev1's entry -> 403 Forbidden
    _switch_user(client, "dev2-doc@dashnode.io")
    res_u2 = client.put(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}",
        json={
            "title": "Intento de hack",
            "category": "Prompt",
            "content": "Hack",
        },
    )
    assert res_u2.status_code == 403

    # 3. Manager marks entry as APPROVED directly in DB
    with Session(db_engine) as session:
        model = session.get(DocumentationEntryModel, entry_id)
        assert model is not None
        model.approval_status = "APPROVED"
        session.commit()

    # 4. Dev1 attempts to edit their already APPROVED entry -> 403 Forbidden
    _switch_user(client, "dev1-doc@dashnode.io")
    res_dev_approved = client.put(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}",
        json={
            "title": "Modificar aprobada",
            "category": "Prompt",
            "content": "Modificado",
        },
    )
    assert res_dev_approved.status_code == 403

    # 5. Manager edits the APPROVED entry -> Success and resets status to PENDING (RN-DOC-05)
    _switch_user(client, "mgr-doc@dashnode.io")
    res_mgr_edit = client.put(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}",
        json={
            "title": "Revisión por Gerente",
            "category": "Prompt",
            "content": "Contenido corregido por Gerencia",
        },
    )
    assert res_mgr_edit.status_code == 200
    assert res_mgr_edit.json()["entry"]["approval_status"] == "PENDING"


def test_hu_79_delete_documentation_entry_soft_delete(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "mgr-doc@dashnode.io")

    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Entrada para Borrar",
            "category": "General",
            "content": "Texto a eliminar",
        },
    )
    entry_id = res_c.json()["entry"]["id"]

    # 1. Developer tries to delete -> 403 Forbidden
    _switch_user(client, "dev1-doc@dashnode.io")
    res_del_dev = client.delete(f"/api/v1/projects/{project_id}/documentation/{entry_id}")
    assert res_del_dev.status_code == 403

    # 2. Manager deletes -> 200 OK
    _switch_user(client, "mgr-doc@dashnode.io")
    res_del_mgr = client.delete(f"/api/v1/projects/{project_id}/documentation/{entry_id}")
    assert res_del_mgr.status_code == 200
    assert res_del_mgr.json()["message"] == messages.ENTRY_DELETED

    # 3. Soft-deleted: Entry no longer listed
    res_list = client.get(f"/api/v1/projects/{project_id}/documentation")
    assert res_list.status_code == 200
    assert len(res_list.json()["entries"]) == 0

    # 4. In DB: row still exists with is_deleted = True
    with Session(db_engine) as session:
        row = session.get(DocumentationEntryModel, entry_id)
        assert row is not None
        assert row.is_deleted is True


def test_hu_80_list_documentation_entries_role_scoping_and_pinning(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # Empty list state
    _switch_user(client, "mgr-doc@dashnode.io")
    res_empty = client.get(f"/api/v1/projects/{project_id}/documentation")
    assert res_empty.status_code == 200
    assert res_empty.json()["entries"] == []
    assert res_empty.json()["message"] == messages.NO_ENTRIES

    # Create 3 entries:
    # Entry 1: Created by Dev 1 (PENDING)
    _switch_user(client, "dev1-doc@dashnode.io")
    e1 = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={"title": "Dev 1 Entry", "category": "Técnica", "content": "Text 1"},
    ).json()["entry"]["id"]

    # Entry 2: Created by Dev 2 (APPROVED)
    _switch_user(client, "dev2-doc@dashnode.io")
    e2 = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={"title": "Dev 2 Entry", "category": "Funcional", "content": "Text 2"},
    ).json()["entry"]["id"]
    with Session(db_engine) as session:
        m2 = session.get(DocumentationEntryModel, e2)
        assert m2 is not None
        m2.approval_status = "APPROVED"
        m2.is_pinned = True  # Pinned!
        session.commit()

    # Entry 3: Created by Dev 2 (PENDING)
    e3 = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={"title": "Dev 2 Secret", "category": "Reunión", "content": "Text 3"},
    ).json()["entry"]["id"]

    # Manager sees ALL 3 entries
    _switch_user(client, "mgr-doc@dashnode.io")
    res_mgr = client.get(f"/api/v1/projects/{project_id}/documentation")
    assert res_mgr.status_code == 200
    mgr_ids = [e["id"] for e in res_mgr.json()["entries"]]
    assert len(mgr_ids) == 3
    # Pinned entry (e2) must be first
    assert mgr_ids[0] == e2

    # Dev 1 sees:
    # - Their own entry (e1 - PENDING)
    # - Approved entry (e2 - APPROVED)
    # - BUT NOT Dev 2's unapproved entry (e3)
    _switch_user(client, "dev1-doc@dashnode.io")
    res_dev1 = client.get(f"/api/v1/projects/{project_id}/documentation")
    assert res_dev1.status_code == 200
    dev1_ids = [e["id"] for e in res_dev1.json()["entries"]]
    assert e1 in dev1_ids
    assert e2 in dev1_ids
    assert e3 not in dev1_ids


def test_hu_81_direct_access_control_denied(client: TestClient, db_engine: Engine) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # Dev 2 creates a PENDING entry
    _switch_user(client, "dev2-doc@dashnode.io")
    res_e = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Borrador Confidencial",
            "category": "Técnica",
            "content": "Secretos de arquitectura",
        },
    )
    entry_id = res_e.json()["entry"]["id"]

    # 1. Dev 1 tries to access Dev 2's unapproved entry directly -> 403 Forbidden with exact message
    _switch_user(client, "dev1-doc@dashnode.io")
    res_denied = client.get(f"/api/v1/projects/{project_id}/documentation/{entry_id}")
    assert res_denied.status_code == 403
    assert res_denied.json()["error"]["message"] == messages.ENTRY_ACCESS_DENIED

    # 2. Dev 2 (author) CAN access it directly
    _switch_user(client, "dev2-doc@dashnode.io")
    res_author = client.get(f"/api/v1/projects/{project_id}/documentation/{entry_id}")
    assert res_author.status_code == 200
    assert res_author.json()["title"] == "Borrador Confidencial"

    # 3. Manager CAN access it directly
    _switch_user(client, "mgr-doc@dashnode.io")
    res_mgr = client.get(f"/api/v1/projects/{project_id}/documentation/{entry_id}")
    assert res_mgr.status_code == 200

    # 4. Non-existent entry -> 404 Not Found
    res_404 = client.get(
        f"/api/v1/projects/{project_id}/documentation/00000000-0000-0000-0000-000000000000"
    )
    assert res_404.status_code == 404


def test_hu_82_toggle_documentation_visibility(client: TestClient, db_engine: Engine) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "mgr-doc@dashnode.io")

    # Create and approve an entry
    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Documento de Integración",
            "category": "Funcional",
            "content": "Contenido funcional",
        },
    )
    entry_id = res_c.json()["entry"]["id"]

    # Pending entry cannot be made visible to devs
    res_err = client.patch(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/visibility",
        json={"is_visible_to_devs": True},
    )
    assert res_err.status_code == 400
    assert res_err.json()["error"]["message"] == messages.VISIBILITY_APPROVED_ONLY

    # Approve entry using direct DB or second manager
    with Session(db_engine) as session:
        m = session.get(DocumentationEntryModel, entry_id)
        assert m is not None
        m.approval_status = "APPROVED"
        m.is_visible_to_devs = True
        session.commit()

    # Dev1 can see it
    _switch_user(client, "dev1-doc@dashnode.io")
    res_l1 = client.get(f"/api/v1/projects/{project_id}/documentation")
    assert any(e["id"] == entry_id for e in res_l1.json()["entries"])

    # Dev1 cannot toggle visibility -> 403
    res_dev_toggle = client.patch(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/visibility",
        json={"is_visible_to_devs": False},
    )
    assert res_dev_toggle.status_code == 403

    # Manager restricts visibility -> 200
    _switch_user(client, "mgr-doc@dashnode.io")
    res_toggle = client.patch(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/visibility",
        json={"is_visible_to_devs": False},
    )
    assert res_toggle.status_code == 200
    assert res_toggle.json()["message"] == messages.VISIBILITY_UPDATED
    assert res_toggle.json()["entry"]["is_visible_to_devs"] is False

    # Dev1 can no longer see it
    _switch_user(client, "dev1-doc@dashnode.io")
    res_l2 = client.get(f"/api/v1/projects/{project_id}/documentation")
    assert not any(e["id"] == entry_id for e in res_l2.json()["entries"])


def test_hu_83_list_pending_approvals_queue(client: TestClient, db_engine: Engine) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)
    _switch_user(client, "dev1-doc@dashnode.io")

    # Dev creates a pending entry
    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Borrador de Tareas",
            "category": "Técnica",
            "content": "Contenido pendiente",
        },
    )
    assert res_c.status_code == 201

    # Dev cannot access pending queue -> 403
    res_dev = client.get(f"/api/v1/projects/{project_id}/documentation/pending-approvals")
    assert res_dev.status_code == 403

    # Manager sees the pending entry
    _switch_user(client, "mgr-doc@dashnode.io")
    res_mgr = client.get(f"/api/v1/projects/{project_id}/documentation/pending-approvals")
    assert res_mgr.status_code == 200
    assert len(res_mgr.json()["entries"]) >= 1


def test_hu_84_approve_documentation_entry_and_self_approval_restriction(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # 1. Manager creates an entry
    _switch_user(client, "mgr-doc@dashnode.io")
    res_mgr_doc = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Documento de Gerente",
            "category": "General",
            "content": "Notas de gestión",
        },
    )
    mgr_entry_id = res_mgr_doc.json()["entry"]["id"]

    # Manager tries to approve OWN entry -> 403 RN-DOC-01
    res_self = client.post(f"/api/v1/projects/{project_id}/documentation/{mgr_entry_id}/approve")
    assert res_self.status_code == 403
    assert res_self.json()["error"]["message"] == messages.CANNOT_APPROVE_OWN_ENTRY

    # 2. Dev creates an entry
    _switch_user(client, "dev1-doc@dashnode.io")
    res_dev_doc = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Documento de Dev",
            "category": "Prompt",
            "content": "Prompts de IA",
        },
    )
    dev_entry_id = res_dev_doc.json()["entry"]["id"]

    # Manager approves Dev's entry -> 200
    _switch_user(client, "mgr-doc@dashnode.io")
    res_app = client.post(f"/api/v1/projects/{project_id}/documentation/{dev_entry_id}/approve")
    assert res_app.status_code == 200
    assert res_app.json()["message"] == messages.ENTRY_APPROVED
    assert res_app.json()["entry"]["approval_status"] == "APPROVED"
    assert res_app.json()["entry"]["is_visible_to_devs"] is True


def test_hu_85_reject_documentation_entry_with_feedback(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # Dev creates entry
    _switch_user(client, "dev1-doc@dashnode.io")
    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Propuesta Rechazable",
            "category": "Técnica",
            "content": "Contenido a mejorar",
        },
    )
    entry_id = res_c.json()["entry"]["id"]

    # Manager rejects it
    _switch_user(client, "mgr-doc@dashnode.io")
    res_rej = client.post(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/reject",
        json={"rejection_reason": "Falta detallar los casos de borde."},
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["message"] == messages.ENTRY_REJECTED
    assert res_rej.json()["entry"]["approval_status"] == "REJECTED"
    assert res_rej.json()["entry"]["rejection_reason"] == "Falta detallar los casos de borde."


def test_hu_86_resubmit_rejected_entry(client: TestClient, db_engine: Engine) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # Dev creates entry
    _switch_user(client, "dev1-doc@dashnode.io")
    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={
            "title": "Propuesta Inicial",
            "category": "Técnica",
            "content": "Borrador 1",
        },
    )
    entry_id = res_c.json()["entry"]["id"]

    # Cannot resubmit when PENDING
    res_invalid = client.post(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/resubmit",
        json={
            "title": "Propuesta Corregida",
            "category": "Técnica",
            "content": "Borrador corregido",
        },
    )
    assert res_invalid.status_code == 400
    assert res_invalid.json()["error"]["message"] == messages.ONLY_REJECTED_CAN_BE_RESUBMITTED

    # Manager rejects it
    _switch_user(client, "mgr-doc@dashnode.io")
    client.post(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/reject",
        json={"rejection_reason": "Corregir formato."},
    )

    # Dev2 cannot resubmit Dev1's rejected entry -> 403
    _switch_user(client, "dev2-doc@dashnode.io")
    res_dev2 = client.post(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/resubmit",
        json={
            "title": "Intruso",
            "category": "Técnica",
            "content": "Intento no permitido",
        },
    )
    assert res_dev2.status_code == 403

    # Dev1 (author) resubmits it successfully -> 200
    _switch_user(client, "dev1-doc@dashnode.io")
    res_ok = client.post(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/resubmit",
        json={
            "title": "Propuesta Final Corregida",
            "category": "Técnica",
            "content": "Contenido completo con casos de borde.",
        },
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["message"] == messages.ENTRY_RESUBMITTED
    assert res_ok.json()["entry"]["approval_status"] == "PENDING"
    assert res_ok.json()["entry"]["rejection_reason"] == "Corregir formato."


def test_hu_87_89_toggle_pin_entry_success_and_ordering(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # Manager creates two entries: older entry_a and newer entry_b
    _switch_user(client, "mgr-doc@dashnode.io")
    res_a = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={"title": "Entrada Primera A", "category": "General", "content": "Contenido A"},
    )
    entry_a_id = res_a.json()["entry"]["id"]

    res_b = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={"title": "Entrada Segunda B", "category": "General", "content": "Contenido B"},
    )
    entry_b_id = res_b.json()["entry"]["id"]

    # Before pinning: newest entry_b is first
    res_list_1 = client.get(f"/api/v1/projects/{project_id}/documentation")
    entries_1 = res_list_1.json()["entries"]
    assert entries_1[0]["id"] == entry_b_id
    assert entries_1[1]["id"] == entry_a_id
    assert entries_1[0]["is_pinned"] is False
    assert entries_1[1]["is_pinned"] is False

    # 1. Manager pins entry_a (HU_DN_06_87, HU_DN_06_89) via PATCH
    res_pin = client.patch(f"/api/v1/projects/{project_id}/documentation/{entry_a_id}/pin")
    assert res_pin.status_code == 200
    assert res_pin.json()["message"] == messages.ENTRY_PINNED
    assert res_pin.json()["entry"]["is_pinned"] is True
    assert res_pin.json()["entry"]["can_pin"] is True

    # Validation: entry_a now appears at the top of the list!
    res_list_2 = client.get(f"/api/v1/projects/{project_id}/documentation")
    entries_2 = res_list_2.json()["entries"]
    assert entries_2[0]["id"] == entry_a_id
    assert entries_2[0]["is_pinned"] is True
    assert entries_2[1]["id"] == entry_b_id

    # 2. Manager unpins entry_a via POST (alternating action)
    res_unpin = client.post(f"/api/v1/projects/{project_id}/documentation/{entry_a_id}/pin")
    assert res_unpin.status_code == 200
    assert res_unpin.json()["message"] == messages.ENTRY_UNPINNED
    assert res_unpin.json()["entry"]["is_pinned"] is False

    # Validation: entry_a returns to its normal position
    res_list_3 = client.get(f"/api/v1/projects/{project_id}/documentation")
    entries_3 = res_list_3.json()["entries"]
    assert entries_3[0]["id"] == entry_b_id
    assert entries_3[1]["id"] == entry_a_id


def test_hu_87_89_toggle_pin_restrictions_and_errors(client: TestClient, db_engine: Engine) -> None:
    project_id, _, _, _ = _setup_project_with_members(client, db_engine)

    # Manager creates an entry
    _switch_user(client, "mgr-doc@dashnode.io")
    res_c = client.post(
        f"/api/v1/projects/{project_id}/documentation",
        json={"title": "Entrada de prueba", "category": "General", "content": "Contenido"},
    )
    entry_id = res_c.json()["entry"]["id"]

    # Developer cannot pin -> 403 Forbidden
    _switch_user(client, "dev1-doc@dashnode.io")
    res_dev_pin = client.patch(f"/api/v1/projects/{project_id}/documentation/{entry_id}/pin")
    assert res_dev_pin.status_code == 403

    # Admin CAN pin and unpin with explicit payload (HU_DN_06_87, HU_DN_06_89)
    create_user(db_engine, email="admin-doc@dashnode.io", role="admin")
    _switch_user(client, "admin-doc@dashnode.io")
    res_admin_pin = client.patch(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/pin",
        json={"is_pinned": True},
    )
    assert res_admin_pin.status_code == 200
    assert res_admin_pin.json()["entry"]["is_pinned"] is True
    assert res_admin_pin.json()["message"] == messages.ENTRY_PINNED

    res_admin_unpin = client.patch(
        f"/api/v1/projects/{project_id}/documentation/{entry_id}/pin",
        json={"is_pinned": False},
    )
    assert res_admin_unpin.status_code == 200
    assert res_admin_unpin.json()["entry"]["is_pinned"] is False
    assert res_admin_unpin.json()["message"] == messages.ENTRY_UNPINNED

    # Non-existent entry -> 404 Not Found
    _switch_user(client, "mgr-doc@dashnode.io")
    res_404 = client.patch(
        f"/api/v1/projects/{project_id}/documentation/00000000-0000-0000-0000-000000000000/pin"
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["message"] == messages.ENTRY_NOT_FOUND
