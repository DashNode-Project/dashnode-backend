"""API integration tests for EP-12 (HU_DN_07_106 .. HU_DN_07_110 AI visual analysis).

@sad Anexo D, DA-01, DA-06, DA-07, DA-08
@origin [User Stories HU_DN_07_106 .. HU_DN_07_110]
"""

import io

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.fixes.domain import messages
from app.modules.projects.infrastructure.models import AuditLogModel
from tests.support import DEFAULT_PASSWORD, create_user, login_as

# Minimal 1x1 valid PNG
VALID_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _switch_user(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 200, res.text


def _setup_project(client: TestClient, db_engine: Engine) -> tuple[str, str, str, str]:
    mgr_id = login_as(client, db_engine, email="mgr-ai-ep12@dashnode.io", role="manager")
    dev1_id = create_user(db_engine, email="dev1-ai-ep12@dashnode.io", role="developer")
    dev2_id = create_user(db_engine, email="dev2-ai-ep12@dashnode.io", role="developer")

    proj = client.post(
        "/api/v1/projects",
        json={
            "name": "EP12 AI Analysis Project",
            "description": "Visual AI analysis testing",
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


def _create_issue_with_image(
    client: TestClient,
    project_id: str,
    title: str = "Error visual en interfaz",
    content: bytes = VALID_PNG,
) -> tuple[str, str]:
    """Create an issue and attach a valid PNG evidence."""
    iss_res = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": title,
            "description": "Fallo en renderizado del componente visual.",
            "severity": "Alta",
            "type": "Bug",
        },
    )
    assert iss_res.status_code == 201, iss_res.text
    issue_id = iss_res.json()["issue"]["id"]

    ev_res = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/evidences",
        files={"file": ("screenshot.png", io.BytesIO(content), "image/png")},
    )
    assert ev_res.status_code == 201, ev_res.text
    evidence_id = ev_res.json()["evidence"]["id"]
    return issue_id, evidence_id


def test_hu_106_request_ai_analysis_and_reuse(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    issue_id, evidence_id = _create_issue_with_image(client, project_id)

    # 1. Reject without privacy confirmation checkbox
    res_no_conf = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={
            "evidence_id": evidence_id,
            "confirmed_no_sensitive_data": False,
        },
    )
    assert res_no_conf.status_code == 400
    assert messages.AI_CONFIRMATION_REQUIRED in res_no_conf.text

    # 2. Reject if issue has no evidence
    iss_no_ev = client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={
            "title": "Issue sin evidencias",
            "description": "Sin capturas",
            "severity": "Media",
            "type": "Bug",
        },
    )
    assert iss_no_ev.status_code == 201
    no_ev_issue_id = iss_no_ev.json()["issue"]["id"]
    res_no_ev = client.post(
        f"/api/v1/projects/{project_id}/issues/{no_ev_issue_id}/ai-analyses",
        json={
            "confirmed_no_sensitive_data": True,
        },
    )
    assert res_no_ev.status_code == 400
    assert messages.NO_EVIDENCE_FOR_ANALYSIS in res_no_ev.text

    # 3. Successful enqueue (202 Accepted)
    res_enq = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={
            "evidence_id": evidence_id,
            "confirmed_no_sensitive_data": True,
        },
    )
    assert res_enq.status_code == 202
    enq_data = res_enq.json()
    analysis_id = enq_data["analysis_id"]
    assert analysis_id
    assert enq_data["reused"] is False
    assert enq_data["message"] == messages.AI_ANALYSIS_REQUESTED

    # 4. Hash reuse (200 OK) with same evidence and prompt version
    res_reuse = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={
            "evidence_id": evidence_id,
            "confirmed_no_sensitive_data": True,
        },
    )
    assert res_reuse.status_code == 200
    reuse_data = res_reuse.json()
    assert reuse_data["analysis_id"] == analysis_id
    assert reuse_data["reused"] is True
    assert reuse_data["message"] == messages.AI_ANALYSIS_REUSED


def test_hu_107_get_analysis_status_and_guardrails(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    issue_id, evidence_id = _create_issue_with_image(client, project_id)

    # Enqueue analysis
    res_enq = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={"evidence_id": evidence_id, "confirmed_no_sensitive_data": True},
    )
    assert res_enq.status_code == 202
    analysis_id = res_enq.json()["analysis_id"]

    # Poll status
    res_poll = client.get(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}"
    )
    assert res_poll.status_code == 200
    status_data = res_poll.json()
    assert status_data["analysis_id"] == analysis_id
    assert status_data["status"] == "DONE"
    assert status_data["requires_human_validation"] is True
    assert status_data["validation_status"] == "PENDING_VALIDATION"

    result = status_data["result"]
    assert result is not None
    assert result["problem_description"]
    assert result["probable_cause"]
    assert result["suggested_solution"]
    assert result["context_sufficient"] is True

    # Word count on server <= 150
    total_words = (
        len(result["problem_description"].split())
        + len(result["probable_cause"].split())
        + len(result["suggested_solution"].split())
    )
    assert total_words <= 150

    # Test fallback when context is insufficient
    no_ctx_issue, no_ctx_ev = _create_issue_with_image(
        client,
        project_id,
        title="Test [SIMULATE_NO_CONTEXT] en vista",
        content=VALID_PNG + b"\x01",
    )
    res_no_ctx = client.post(
        f"/api/v1/projects/{project_id}/issues/{no_ctx_issue}/ai-analyses",
        json={
            "evidence_id": no_ctx_ev,
            "confirmed_no_sensitive_data": True,
            "force_new": True,
        },
    )
    assert res_no_ctx.status_code == 202
    no_ctx_id = res_no_ctx.json()["analysis_id"]

    res_no_ctx_status = client.get(
        f"/api/v1/projects/{project_id}/issues/{no_ctx_issue}/ai-analyses/{no_ctx_id}"
    )
    assert res_no_ctx_status.status_code == 200
    no_ctx_data = res_no_ctx_status.json()
    assert no_ctx_data["result"]["context_sufficient"] is False
    assert no_ctx_data["result"]["suggested_solution"] is None


def test_hu_108_list_ai_analyses_and_membership(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    issue_id, evidence_id = _create_issue_with_image(client, project_id)

    # Empty state before analysis
    res_empty = client.get(f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses")
    assert res_empty.status_code == 200
    empty_data = res_empty.json()
    assert empty_data["items"] == []

    # Enqueue analysis
    client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={"evidence_id": evidence_id, "confirmed_no_sensitive_data": True},
    )

    # Query list
    res_list = client.get(f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data["items"]) == 1
    item = list_data["items"][0]
    assert item["requested_by"]["id"] == dev1_id
    assert item["validation_status"] == "PENDING_VALIDATION"
    assert item["summary"]
    assert item["result"] is not None

    # Non-member access rejected
    create_user(db_engine, email="outsider-ep12@dashnode.io", role="developer")
    _switch_user(client, "outsider-ep12@dashnode.io")
    res_forbidden = client.get(f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses")
    assert res_forbidden.status_code == 403


def test_hu_109_delete_ai_analysis_and_audit(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, dev1_id, _dev2_id = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    issue_id, evidence_id = _create_issue_with_image(client, project_id)
    res_enq = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={"evidence_id": evidence_id, "confirmed_no_sensitive_data": True},
    )
    analysis_id = res_enq.json()["analysis_id"]

    # 1. Dev2 (not requester, not manager/admin) cannot delete -> 403
    _switch_user(client, "dev2-ai-ep12@dashnode.io")
    res_del_dev2 = client.delete(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}"
    )
    assert res_del_dev2.status_code == 403
    assert messages.AI_DELETE_FORBIDDEN in res_del_dev2.text

    # 2. Requester (Dev1) can delete -> 200
    _switch_user(client, "dev1-ai-ep12@dashnode.io")
    res_del_ok = client.delete(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}"
    )
    assert res_del_ok.status_code == 200
    assert res_del_ok.json()["message"] == messages.AI_ANALYSIS_DELETED

    # 3. Excluded from active list
    res_list_after = client.get(f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses")
    assert res_list_after.status_code == 200
    assert res_list_after.json()["items"] == []

    # 4. Verify audit log entry exists
    with Session(db_engine) as session:
        log = session.scalars(
            select(AuditLogModel).where(
                AuditLogModel.resource_type == "ai_analysis",
                AuditLogModel.resource_id == analysis_id,
            )
        ).first()
        assert log is not None
        assert log.action == "ai_analysis.deleted"
        assert log.user_id == dev1_id


def test_hu_110_error_mappings_and_retry(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    # 1. Timeout simulation
    iss_timeout, ev_timeout = _create_issue_with_image(
        client, project_id, title="Issue [SIMULATE_TIMEOUT]"
    )
    res_to = client.post(
        f"/api/v1/projects/{project_id}/issues/{iss_timeout}/ai-analyses",
        json={"evidence_id": ev_timeout, "confirmed_no_sensitive_data": True},
    )
    assert res_to.status_code == 202
    to_id = res_to.json()["analysis_id"]

    res_to_status = client.get(
        f"/api/v1/projects/{project_id}/issues/{iss_timeout}/ai-analyses/{to_id}"
    )
    assert res_to_status.status_code == 200
    to_data = res_to_status.json()
    assert to_data["status"] == "FAILED"
    assert to_data["error_code"] == "AI_TIMEOUT"
    assert to_data["message"] == messages.AI_TIMEOUT
    assert to_data["retryable"] is True

    # 2. Quota exhausted simulation
    iss_quota, ev_quota = _create_issue_with_image(
        client, project_id, title="Issue [SIMULATE_QUOTA_EXHAUSTED]"
    )
    res_q = client.post(
        f"/api/v1/projects/{project_id}/issues/{iss_quota}/ai-analyses",
        json={"evidence_id": ev_quota, "confirmed_no_sensitive_data": True},
    )
    assert res_q.status_code == 202
    q_id = res_q.json()["analysis_id"]

    res_q_status = client.get(
        f"/api/v1/projects/{project_id}/issues/{iss_quota}/ai-analyses/{q_id}"
    )
    assert res_q_status.status_code == 200
    q_data = res_q_status.json()
    assert q_data["status"] == "FAILED"
    assert q_data["error_code"] == "AI_QUOTA_EXHAUSTED"
    assert q_data["message"] == messages.AI_QUOTA_EXHAUSTED
    assert q_data["retryable"] is True

    # 3. Provider error simulation
    iss_pe, ev_pe = _create_issue_with_image(
        client, project_id, title="Issue [SIMULATE_PROVIDER_ERROR]"
    )
    res_pe = client.post(
        f"/api/v1/projects/{project_id}/issues/{iss_pe}/ai-analyses",
        json={"evidence_id": ev_pe, "confirmed_no_sensitive_data": True},
    )
    assert res_pe.status_code == 202
    pe_id = res_pe.json()["analysis_id"]

    res_pe_status = client.get(f"/api/v1/projects/{project_id}/issues/{iss_pe}/ai-analyses/{pe_id}")
    assert res_pe_status.status_code == 200
    pe_data = res_pe_status.json()
    assert pe_data["status"] == "FAILED"
    assert pe_data["error_code"] == "AI_PROVIDER_ERROR"
    assert pe_data["message"] == messages.AI_PROVIDER_ERROR
    assert pe_data["retryable"] is True


def test_hu_111_validate_ai_analysis_api(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    issue_id, ev_id = _create_issue_with_image(client, project_id, title="Issue for Validate")
    res = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={"evidence_id": ev_id, "confirmed_no_sensitive_data": True},
    )
    assert res.status_code == 202
    analysis_id = res.json()["analysis_id"]

    # 1. Developer tries to validate -> 403 Forbidden (RN-IAG-03)
    val_dev = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/validate"
    )
    assert val_dev.status_code == 403
    assert val_dev.json()["error"]["message"] == messages.AI_VALIDATE_FORBIDDEN

    # 2. Manager validates -> 200 OK
    _switch_user(client, "mgr-ai-ep12@dashnode.io")
    val_mgr = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/validate"
    )
    assert val_mgr.status_code == 200
    assert val_mgr.json()["message"] == messages.AI_VALIDATE_SUCCESS
    assert val_mgr.json()["validation_status"] == "VALIDATED"

    # 3. Repeat validate -> 409 Conflict
    val_mgr_rep = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/validate"
    )
    assert val_mgr_rep.status_code == 409
    assert val_mgr_rep.json()["error"]["code"] == "INVALID_VALIDATION_STATE"
    assert val_mgr_rep.json()["error"]["message"] == messages.AI_VALIDATE_INVALID_STATE


def test_hu_112_reject_ai_analysis_api(client: TestClient, db_engine: Engine) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "dev1-ai-ep12@dashnode.io")

    issue_id, ev_id = _create_issue_with_image(client, project_id, title="Issue for Reject")
    res = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={"evidence_id": ev_id, "confirmed_no_sensitive_data": True},
    )
    assert res.status_code == 202
    analysis_id = res.json()["analysis_id"]

    # 1. Developer tries to reject -> 403 Forbidden
    rej_dev = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/reject"
    )
    assert rej_dev.status_code == 403
    assert rej_dev.json()["error"]["message"] == messages.AI_REJECT_FORBIDDEN

    # 2. Manager rejects from PENDING -> 200 OK
    _switch_user(client, "mgr-ai-ep12@dashnode.io")
    rej_mgr = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/reject",
        json={"reason": "Recomendación no aplicable"},
    )
    assert rej_mgr.status_code == 200
    assert rej_mgr.json()["message"] == messages.AI_REJECT_SUCCESS
    assert rej_mgr.json()["validation_status"] == "REJECTED"

    # 3. Repeat reject on already rejected -> 409 Conflict
    rej_mgr_rep = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/reject"
    )
    assert rej_mgr_rep.status_code == 409
    assert rej_mgr_rep.json()["error"]["code"] == "INVALID_VALIDATION_STATE"
    assert rej_mgr_rep.json()["error"]["message"] == messages.AI_REJECT_INVALID_STATE

    # 4. Reject from VALIDATED (correction of previous validation)
    iss_val_id, ev_val_id = _create_issue_with_image(
        client, project_id, title="Issue for Validated Reject"
    )
    res_val = client.post(
        f"/api/v1/projects/{project_id}/issues/{iss_val_id}/ai-analyses",
        json={"evidence_id": ev_val_id, "confirmed_no_sensitive_data": True, "force_new": True},
    )
    assert res_val.status_code in (200, 202)
    an_val_id = res_val.json()["analysis_id"]

    # First validate
    val_res = client.post(
        f"/api/v1/projects/{project_id}/issues/{iss_val_id}/ai-analyses/{an_val_id}/validate"
    )
    assert val_res.status_code == 200

    # Then reject
    rej_from_val = client.post(
        f"/api/v1/projects/{project_id}/issues/{iss_val_id}/ai-analyses/{an_val_id}/reject"
    )
    assert rej_from_val.status_code == 200
    assert rej_from_val.json()["validation_status"] == "REJECTED"


def test_hu_113_ai_human_validation_notice_and_response_fields(
    client: TestClient, db_engine: Engine
) -> None:
    project_id, _mgr_id, _dev1_id, _ = _setup_project(client, db_engine)
    _switch_user(client, "mgr-ai-ep12@dashnode.io")

    issue_id, ev_id = _create_issue_with_image(client, project_id, title="Issue for HU 113")
    res = client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses",
        json={"evidence_id": ev_id, "confirmed_no_sensitive_data": True},
    )
    analysis_id = res.json()["analysis_id"]

    # 1. While PENDING_VALIDATION: requires_human_validation is True
    status_pending = client.get(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}"
    )
    assert status_pending.status_code == 200
    assert status_pending.json()["requires_human_validation"] is True
    assert status_pending.json()["validation_status"] == "PENDING_VALIDATION"
    assert status_pending.json()["validated_by_name"] is None

    # 2. Validate it
    client.post(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/validate"
    )

    status_validated = client.get(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}"
    )
    assert status_validated.status_code == 200
    assert status_validated.json()["requires_human_validation"] is False
    assert status_validated.json()["validation_status"] == "VALIDATED"
    assert status_validated.json()["validated_by_name"] is not None
    assert status_validated.json()["validated_at"] is not None

    # 3. Reject it
    client.post(f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}/reject")

    status_rejected = client.get(
        f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses/{analysis_id}"
    )
    assert status_rejected.status_code == 200
    assert status_rejected.json()["requires_human_validation"] is True
    assert status_rejected.json()["validation_status"] == "REJECTED"
    assert status_rejected.json()["rejected_by_name"] is not None
    assert status_rejected.json()["rejected_at"] is not None

    # 4. Check list endpoint incorporates requires_human_validation and names
    list_res = client.get(f"/api/v1/projects/{project_id}/issues/{issue_id}/ai-analyses")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) >= 1
    item = next(it for it in items if it["id"] == analysis_id)
    assert item["requires_human_validation"] is True
    assert item["validation_status"] == "REJECTED"
    assert item["rejected_by_name"] is not None
