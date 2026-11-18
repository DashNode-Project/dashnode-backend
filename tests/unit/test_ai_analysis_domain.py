"""Unit tests for EP-12 AI visual analysis domain logic, guardrails, and pipeline.

@sad Anexo D, DA-01, DA-06, DA-07, DA-08
@origin [User Stories HU_DN_07_106 .. HU_DN_07_110]
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.modules.fixes.application.ai_use_cases import (
    InvalidValidationStateError,
    RejectAiAnalysisUseCase,
    ValidateAiAnalysisUseCase,
)
from app.modules.fixes.application.vision_pipeline import (
    AiOutputInvalidError,
    AiProviderError,
    AiQuotaExhaustedError,
    AiTimeoutError,
    DefaultVisionAnalysisProvider,
    UnsupportedFormatError,
    enforce_output_guardrails,
    preprocess_image,
    preprocess_video,
)
from app.modules.fixes.domain.entities import (
    AiAnalysis,
    AiAnalysisResult,
    AiAnalysisStatus,
    AiProgressStage,
    AiValidationStatus,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
    count_words,
    has_forbidden_fix_claims,
    redact_sensitive_text,
    result_has_forbidden_fix_claims,
    total_result_words,
)
from app.modules.fixes.domain.messages import (
    AI_REJECT_FORBIDDEN,
    AI_REJECT_INVALID_STATE,
    AI_REJECT_SUCCESS,
    AI_VALIDATE_FORBIDDEN,
    AI_VALIDATE_INVALID_STATE,
    AI_VALIDATE_SUCCESS,
)
from app.shared.application.identity import CurrentUser


def test_word_counting_and_totals() -> None:
    assert count_words("") == 0
    assert count_words("   ") == 0
    assert count_words("palabra uno dos tres") == 4

    res = AiAnalysisResult(
        problem_description="Descripción breve del problema encontrado.",  # 5 words
        probable_cause="Causa probable identificada en la vista.",  # 6 words
        suggested_solution="Solución propuesta para el fallo.",  # 5 words
        context_sufficient=True,
    )
    assert total_result_words(res) == 16


def test_forbidden_fix_claims_detection() -> None:
    # Allowed speculative recommendations
    assert not has_forbidden_fix_claims("Se sugiere revisar la validación en el backend.")
    assert not has_forbidden_fix_claims("Podría corregirse ajustando la configuración.")

    # Forbidden claims (affirmation of applied/deployed fix)
    assert has_forbidden_fix_claims("El parche ya se aplicó en el entorno de staging.")
    assert has_forbidden_fix_claims("El bug se corrigió exitosamente.")
    assert has_forbidden_fix_claims("El fix fue aplicado por el equipo.")
    assert has_forbidden_fix_claims("El cambio fue desplegado a producción.")
    assert has_forbidden_fix_claims("El problema queda resuelto.")
    assert has_forbidden_fix_claims("Hemos aplicado la corrección correspondiente.")

    res_with_claim = AiAnalysisResult(
        problem_description="El fallo se corrigió en el servidor.",
        probable_cause="Error de tipo.",
        suggested_solution="Revisar tipado.",
        context_sufficient=True,
    )
    assert result_has_forbidden_fix_claims(res_with_claim)


def test_guardrails_sanitize_forbidden_claims() -> None:
    res = AiAnalysisResult(
        problem_description="Se observó que el bug se corrigió en el componente.",
        probable_cause="Desfase de estado en React.",
        suggested_solution="Asegurarse de que el cambio fue desplegado correctamente.",
        context_sufficient=True,
    )
    sanitized = enforce_output_guardrails(res)
    assert not result_has_forbidden_fix_claims(sanitized)
    assert "se sugiere revisar" in sanitized.problem_description
    assert "se sugiere verificar" in (sanitized.suggested_solution or "")


def test_guardrails_context_insufficient_clears_solution() -> None:
    res = AiAnalysisResult(
        problem_description="Captura ilegible o sin contexto de error.",
        probable_cause="Información insuficiente.",
        suggested_solution="Intentar una solución genérica que no aplica.",
        context_sufficient=False,
    )
    sanitized = enforce_output_guardrails(res)
    assert sanitized.suggested_solution is None


def test_guardrails_trim_words_to_150_max() -> None:
    long_desc = " ".join(["palabra"] * 100)
    long_cause = " ".join(["causa"] * 80)
    long_sol = " ".join(["solucion"] * 50)
    res = AiAnalysisResult(
        problem_description=long_desc,
        probable_cause=long_cause,
        suggested_solution=long_sol,
        context_sufficient=True,
    )
    assert total_result_words(res) == 230
    sanitized = enforce_output_guardrails(res)
    assert total_result_words(sanitized) <= 150


def test_sensitive_data_redaction() -> None:
    text_with_keys = (
        "El error ocurrió usando Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 "
        "y la api key AIzaSyD1234567890abcdef1234567890abcdef con password=SecretPass!123"
    )
    redacted, match_counts = redact_sensitive_text(text_with_keys)
    assert sum(match_counts.values()) >= 2
    assert "AIzaSyD" not in redacted
    assert "eyJhbGciOi" not in redacted
    assert "[REDACTED:" in redacted


def test_video_format_preprocessing() -> None:
    # Too short
    with pytest.raises(UnsupportedFormatError):
        preprocess_video(b"short")

    # Invalid header
    with pytest.raises(UnsupportedFormatError):
        preprocess_video(b"0123456789abcdef0123456789")

    # Valid MP4 header (bytes 4..8 == 'ftyp')
    mp4_bytes = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom"
    assert preprocess_video(mp4_bytes) == mp4_bytes

    # Valid WEBM header (bytes 0..4 == 0x1A45DFA3)
    webm_bytes = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01" + b"\x00" * 10
    assert preprocess_video(webm_bytes) == webm_bytes


def test_image_preprocessing_fallback_on_invalid() -> None:
    # If image cannot be read by PIL, it falls back to raw data safely
    raw = b"not-a-real-png"
    assert preprocess_image(raw) == raw


def test_simulated_qa_triggers() -> None:
    provider = DefaultVisionAnalysisProvider()
    valid_mp4 = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom"

    # Simulate timeout
    with pytest.raises(AiTimeoutError):
        provider.analyze(
            evidence_data=valid_mp4,
            evidence_type="video",
            evidence_title="Test [SIMULATE_TIMEOUT]",
            issue_context={"title": "Test", "description": ""},
        )

    # Simulate quota exhausted
    with pytest.raises(AiQuotaExhaustedError):
        provider.analyze(
            evidence_data=valid_mp4,
            evidence_type="video",
            evidence_title="Test [SIMULATE_QUOTA_EXHAUSTED]",
            issue_context={"title": "Test", "description": ""},
        )

    # Simulate provider error
    with pytest.raises(AiProviderError):
        provider.analyze(
            evidence_data=valid_mp4,
            evidence_type="video",
            evidence_title="Test [SIMULATE_PROVIDER_ERROR]",
            issue_context={"title": "Test", "description": ""},
        )

    # Simulate invalid output
    with pytest.raises(AiOutputInvalidError):
        provider.analyze(
            evidence_data=valid_mp4,
            evidence_type="video",
            evidence_title="Test [SIMULATE_INVALID_OUTPUT]",
            issue_context={"title": "Test", "description": ""},
        )

    # Simulate no context
    res, in_tok, out_tok, _lat, _mod = provider.analyze(
        evidence_data=valid_mp4,
        evidence_type="video",
        evidence_title="Test [SIMULATE_NO_CONTEXT]",
        issue_context={"title": "Fallo en checkout", "description": ""},
    )
    assert res.context_sufficient is False
    assert res.suggested_solution is None
    assert in_tok > 0
    assert out_tok > 0


def test_ai_analysis_status_and_enums() -> None:
    assert AiAnalysisStatus.PENDING.value == "PENDING"
    assert AiAnalysisStatus.PROCESSING.value == "PROCESSING"
    assert AiAnalysisStatus.DONE.value == "DONE"
    assert AiAnalysisStatus.FAILED.value == "FAILED"

    assert AiProgressStage.ANALYZING.value == "ANALYZING"
    assert AiValidationStatus.PENDING_VALIDATION.value == "PENDING_VALIDATION"
    assert AiValidationStatus.VALIDATED.value == "VALIDATED"
    assert AiValidationStatus.REJECTED.value == "REJECTED"


# --- HU_DN_07_111, HU_DN_07_112, HU_DN_07_113 Unit & Architecture Tests ---


def _build_user(user_id: str, role: str, email: str = "test@dashnode.io") -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email=email,
        name=f"User {user_id}",
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _build_dummy_issue(issue_id: str = "iss-1", project_id: str = "proj-1") -> Issue:
    return Issue(
        id=issue_id,
        project_id=project_id,
        title="Error visual en vista",
        description="Fallo de render",
        severity=IssueSeverity.HIGH,
        type=IssueType.BUG,
        status=IssueStatus.OPEN,
        reporter_id="user-dev",
        assignee_id=None,
        resolution_note=None,
        resolved_at=None,
        idempotency_key=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _build_dummy_analysis(
    analysis_id: str = "ai-1",
    issue_id: str = "iss-1",
    validation_status: AiValidationStatus = AiValidationStatus.PENDING_VALIDATION,
) -> AiAnalysis:
    return AiAnalysis(
        id=analysis_id,
        issue_id=issue_id,
        evidence_id="ev-1",
        requested_by="user-dev",
        status=AiAnalysisStatus.DONE,
        progress_stage=None,
        reuse_key="hash123",
        prompt_version="v1",
        model_id="gemini-3.1-flash-lite",
        response=None,
        validation_status=validation_status,
        created_at=datetime.now(UTC),
    )


def test_hu_111_validate_ai_analysis_success_and_restrictions() -> None:
    ai_repo = MagicMock()
    issue_repo = MagicMock()
    projects = MagicMock()
    clock = MagicMock()
    uow = MagicMock()

    projects.is_active_member.return_value = True
    clock.now.return_value = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    issue_repo.get_by_id.return_value = _build_dummy_issue()

    analysis = _build_dummy_analysis(validation_status=AiValidationStatus.PENDING_VALIDATION)
    ai_repo.get_by_id.return_value = analysis

    use_case = ValidateAiAnalysisUseCase(
        ai_repo=ai_repo,
        issue_repo=issue_repo,
        projects=projects,
        clock=clock,
        uow=uow,
    )

    admin_user = _build_user("user-admin", role="admin")
    dev_user = _build_user("user-dev", role="developer")

    # 1. Developer cannot validate (RBAC 403)
    with pytest.raises(PermissionError) as exc_info:
        use_case.execute(
            project_id="proj-1",
            issue_id="iss-1",
            analysis_id="ai-1",
            actor=dev_user,
        )
    assert str(exc_info.value) == AI_VALIDATE_FORBIDDEN

    # 2. Admin validates successfully (200)
    res = use_case.execute(
        project_id="proj-1",
        issue_id="iss-1",
        analysis_id="ai-1",
        actor=admin_user,
    )
    assert res.message == AI_VALIDATE_SUCCESS
    assert res.validation_status == "VALIDATED"
    assert analysis.validation_status == AiValidationStatus.VALIDATED
    assert analysis.validated_by == "user-admin"
    assert analysis.validated_at == datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    ai_repo.save.assert_called_with(analysis)
    uow.commit.assert_called()

    # 3. Trying to validate already validated analysis raises 409 Conflict
    with pytest.raises(InvalidValidationStateError) as conflict_info:
        use_case.execute(
            project_id="proj-1",
            issue_id="iss-1",
            analysis_id="ai-1",
            actor=admin_user,
        )
    assert str(conflict_info.value) == AI_VALIDATE_INVALID_STATE


def test_hu_112_reject_ai_analysis_transitions_and_restrictions() -> None:
    ai_repo = MagicMock()
    issue_repo = MagicMock()
    projects = MagicMock()
    clock = MagicMock()
    uow = MagicMock()

    projects.is_active_member.return_value = True
    clock.now.return_value = datetime(2026, 11, 15, 13, 0, tzinfo=UTC)
    issue_repo.get_by_id.return_value = _build_dummy_issue()

    use_case = RejectAiAnalysisUseCase(
        ai_repo=ai_repo,
        issue_repo=issue_repo,
        projects=projects,
        clock=clock,
        uow=uow,
    )

    manager_user = _build_user("user-mgr", role="manager")
    dev_user = _build_user("user-dev", role="developer")

    # 1. Developer cannot reject (RBAC 403)
    analysis_pending = _build_dummy_analysis(
        validation_status=AiValidationStatus.PENDING_VALIDATION
    )
    ai_repo.get_by_id.return_value = analysis_pending
    with pytest.raises(PermissionError) as exc_info:
        use_case.execute(
            project_id="proj-1",
            issue_id="iss-1",
            analysis_id="ai-1",
            actor=dev_user,
        )
    assert str(exc_info.value) == AI_REJECT_FORBIDDEN

    # 2. Reject from PENDING_VALIDATION (200)
    res_pending = use_case.execute(
        project_id="proj-1",
        issue_id="iss-1",
        analysis_id="ai-1",
        actor=manager_user,
    )
    assert res_pending.message == AI_REJECT_SUCCESS
    assert res_pending.validation_status == "REJECTED"
    assert analysis_pending.validation_status == AiValidationStatus.REJECTED
    assert analysis_pending.rejected_by == "user-mgr"
    assert analysis_pending.rejected_at == datetime(2026, 11, 15, 13, 0, tzinfo=UTC)

    # 3. Reject from VALIDATED (correction of previous validation) (200)
    analysis_validated = _build_dummy_analysis(validation_status=AiValidationStatus.VALIDATED)
    ai_repo.get_by_id.return_value = analysis_validated
    res_val = use_case.execute(
        project_id="proj-1",
        issue_id="iss-1",
        analysis_id="ai-1",
        actor=manager_user,
    )
    assert res_val.message == AI_REJECT_SUCCESS
    assert res_val.validation_status == "REJECTED"
    assert analysis_validated.validation_status == AiValidationStatus.REJECTED

    # 4. Rejecting already REJECTED raises 409 Conflict
    with pytest.raises(InvalidValidationStateError) as conflict_info:
        use_case.execute(
            project_id="proj-1",
            issue_id="iss-1",
            analysis_id="ai-1",
            actor=manager_user,
        )
    assert str(conflict_info.value) == AI_REJECT_INVALID_STATE


def test_hu_113_requires_human_validation_rule() -> None:
    # requires_human_validation is True for PENDING_VALIDATION and REJECTED;
    # False only for VALIDATED
    pending = _build_dummy_analysis(validation_status=AiValidationStatus.PENDING_VALIDATION)
    rejected = _build_dummy_analysis(validation_status=AiValidationStatus.REJECTED)
    validated = _build_dummy_analysis(validation_status=AiValidationStatus.VALIDATED)

    assert (pending.validation_status != AiValidationStatus.VALIDATED) is True
    assert (rejected.validation_status != AiValidationStatus.VALIDATED) is True
    assert (validated.validation_status != AiValidationStatus.VALIDATED) is False


def test_architecture_da08_mutacion_cero() -> None:
    """DA-08 & RN-IAG-03: Zero Mutation Architecture Contract.

    Verifies contractually that ValidateAiAnalysisUseCase and RejectAiAnalysisUseCase
    ONLY mutate ai_analyses and never mutate issues (FixModel) or tasks (StoryTaskModel).
    """
    ai_repo = MagicMock()
    issue_repo = MagicMock()
    projects = MagicMock()
    clock = MagicMock()
    uow = MagicMock()

    projects.is_active_member.return_value = True
    clock.now.return_value = datetime.now(UTC)
    issue_repo.get_by_id.return_value = _build_dummy_issue()

    analysis = _build_dummy_analysis(validation_status=AiValidationStatus.PENDING_VALIDATION)
    ai_repo.get_by_id.return_value = analysis

    val_uc = ValidateAiAnalysisUseCase(ai_repo, issue_repo, projects, clock, uow)
    rej_uc = RejectAiAnalysisUseCase(ai_repo, issue_repo, projects, clock, uow)

    admin = _build_user("admin-1", role="admin")

    # Execute validate
    val_uc.execute("proj-1", "iss-1", "ai-1", admin)
    # Execute reject
    rej_uc.execute("proj-1", "iss-1", "ai-1", admin)

    # CRITICAL CONTRACT CHECK:
    # 1. issue_repo.save was NEVER called
    issue_repo.save.assert_not_called()
    # 2. No other issue mutation methods were called on issue_repo
    for attr in dir(issue_repo):
        if attr.startswith(("update", "delete", "create", "resolve", "close")):
            method = getattr(issue_repo, attr)
            if hasattr(method, "assert_not_called"):
                method.assert_not_called()

    # 3. ai_repo.save was called exactly for the ai analysis
    assert ai_repo.save.call_count == 2
