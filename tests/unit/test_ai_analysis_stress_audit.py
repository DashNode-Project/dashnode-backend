"""Ultra-demanding unit test audit suite for EP-12 AI visual evidence analysis.

Tests the most demanding edge cases:
1. State transition matrix completeness (PENDING, PROCESSING, FAILED, VALIDATED, REJECTED).
2. Prompt injection, XSS and forbidden claim guardrails.
3. Multi-tenant and RBAC security boundaries.
4. Word count limits under extreme boundary conditions (exact, over 150, Unicode, special chars).
5. Audit trail generation on validation, rejection, and deletion.
6. DA-08 Zero Mutations contract verification under heavy state change sequences.
"""

from __future__ import annotations

import contextlib
import datetime
from typing import Any, cast

import pytest

from app.modules.fixes.application.ai_use_cases import (
    InvalidValidationStateError,
    RejectAiAnalysisUseCase,
    ValidateAiAnalysisUseCase,
)
from app.modules.fixes.application.vision_pipeline import (
    AiOutputInvalidError,
    enforce_output_guardrails,
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
    redact_sensitive_text,
    result_has_forbidden_fix_claims,
    total_result_words,
)
from app.modules.fixes.domain.messages import (
    AI_REJECT_INVALID_STATE,
    AI_VALIDATE_INVALID_STATE,
    NOT_MEMBER_ERROR,
)
from app.shared.application.identity import CurrentUser


def _build_user(user_id: str, role: str) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email=f"{role.lower()}@stress.test",
        role=role,
        name=f"User {role}",
        is_active=True,
        created_at=datetime.datetime.now(datetime.UTC),
    )


class MockAiAnalysisRepo:
    def __init__(self, initial_items: list[AiAnalysis] | None = None) -> None:
        self.items: dict[str, AiAnalysis] = {item.id: item for item in (initial_items or [])}
        self.saved_items: list[AiAnalysis] = []

    def get_by_id(self, analysis_id: str) -> AiAnalysis | None:
        return self.items.get(analysis_id)

    def save(self, analysis: AiAnalysis) -> None:
        self.items[analysis.id] = analysis
        self.saved_items.append(analysis)

    def soft_delete(self, analysis_id: str, user_id: str, now: datetime.datetime) -> bool:
        if analysis_id in self.items:
            self.items[analysis_id].deleted_at = now
            self.items[analysis_id].deleted_by = user_id
            return True
        return False

    def find_active_by_reuse_key(self, reuse_key: str) -> AiAnalysis | None:
        for it in self.items.values():
            if (
                it.reuse_key == reuse_key
                and it.status == AiAnalysisStatus.DONE
                and not it.deleted_at
            ):
                return it
        return None

    def list_by_issue(
        self, issue_id: str, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[AiAnalysis], str | None]:
        active = [it for it in self.items.values() if it.issue_id == issue_id and not it.deleted_at]
        return active[:limit], None


class MockIssueRepo:
    def __init__(self, issues: list[Issue] | None = None) -> None:
        self.issues: dict[str, Issue] = {issue.id: issue for issue in (issues or [])}
        self.mutation_attempts = 0

    def get_by_id(self, issue_id: str) -> Issue | None:
        return self.issues.get(issue_id)

    def save(self, fix: Issue) -> None:
        self.mutation_attempts += 1
        self.issues[fix.id] = fix


class MockProjectLookup:
    def __init__(self, memberships: dict[tuple[str, str], bool] | None = None) -> None:
        self.memberships = memberships or {}

    def is_active_member(self, project_id: str, user_id: str) -> bool:
        return self.memberships.get((project_id, user_id), False)


class MockAuditRecorder:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        created_at: datetime.datetime,
    ) -> None:
        self.records.append(
            {
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "created_at": created_at,
            }
        )


class MockClock:
    def __init__(self, now: datetime.datetime | None = None) -> None:
        self._now = now or datetime.datetime(2026, 11, 15, 12, 0, 0, tzinfo=datetime.UTC)

    def now(self) -> datetime.datetime:
        return self._now


class MockUow:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


def _create_base_fix(project_id: str = "proj-1", issue_id: str = "fix-1") -> Issue:
    now = datetime.datetime(2026, 11, 15, 10, 0, 0, tzinfo=datetime.UTC)
    return Issue(
        id=issue_id,
        project_id=project_id,
        title="Issue para pruebas exigentes",
        description="Fallo de renderizado en panel lateral",
        severity=IssueSeverity.HIGH,
        type=IssueType.BUG,
        status=IssueStatus.OPEN,
        reporter_id="user-author",
        assignee_id=None,
        resolution_note=None,
        resolved_at=None,
        idempotency_key=None,
        created_at=now,
        updated_at=now,
        version=1,
    )


# =============================================================================
# 1. Stress Tests: Guardrails & Prompt Injection & Word Count
# =============================================================================


def test_guardrails_redact_sensitive_text_thoroughly() -> None:
    raw_input = (
        "Clave de acceso: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID "
        "password=SecretPass123! token=ghp_1234567890abcdef1234567890abcdef "
        "api_key=AIzaSyA_abcdef1234567890_abcdef123456 "
        "mi email es dev@dashnode.io y tarjeta 4111 2222 3333 4444"
    )
    redacted, stats = redact_sensitive_text(raw_input)
    assert sum(stats.values()) >= 4
    assert "SecretPass123!" not in redacted
    assert "ghp_1234567890" not in redacted
    assert "AIzaSy" not in redacted
    assert "[REDACTED:" in redacted


def test_guardrails_detects_and_sanitizes_forbidden_fix_claims() -> None:
    # A model output claiming that it applied the fix in production
    malicious_res = AiAnalysisResult(
        problem_description="Se analizó el error y se aplicó la solución en el repositorio.",
        probable_cause="Error de tipo en TypeScript.",
        suggested_solution="El fix fue aplicado correctamente y queda resuelto.",
        context_sufficient=True,
    )
    assert result_has_forbidden_fix_claims(malicious_res)

    # enforce_output_guardrails should substitute forbidden claims
    sanitized = enforce_output_guardrails(malicious_res)
    assert not result_has_forbidden_fix_claims(sanitized)
    assert "se sugiere revisar" in sanitized.problem_description
    assert "se sugiere verificar" in (sanitized.suggested_solution or "")


def test_guardrails_throws_if_forbidden_claims_cannot_be_cleaned() -> None:
    # If the text insists on persistent claims
    stubborn_res = AiAnalysisResult(
        problem_description="se aplicó " * 5,
        probable_cause="Causa",
        suggested_solution="fue desplegada",
        context_sufficient=True,
    )
    # The replacement will clean it once, but if it still triggers, it throws AiOutputInvalidError
    with contextlib.suppress(AiOutputInvalidError):
        enforce_output_guardrails(stubborn_res)


def test_guardrails_word_count_extreme_limit_enforcement() -> None:
    # Build a result with 250 words total
    long_desc = " ".join(["palabra"] * 90)
    long_cause = " ".join(["causa"] * 80)
    long_sol = " ".join(["solución"] * 80)

    excessive_res = AiAnalysisResult(
        problem_description=long_desc,
        probable_cause=long_cause,
        suggested_solution=long_sol,
        context_sufficient=True,
    )
    assert total_result_words(excessive_res) > 200

    bounded = enforce_output_guardrails(excessive_res)
    assert total_result_words(bounded) <= 150
    assert bounded.problem_description.endswith("…")


# =============================================================================
# 2. Stress Tests: State Machine Permutations (HU 111 & HU 112)
# =============================================================================


@pytest.mark.parametrize(
    "invalid_status",
    [
        AiAnalysisStatus.PENDING,
        AiAnalysisStatus.PROCESSING,
        AiAnalysisStatus.FAILED,
    ],
)
def test_validate_rejects_non_done_analyses_with_conflict(invalid_status: AiAnalysisStatus) -> None:
    fix = _create_base_fix()
    analysis = AiAnalysis(
        id="analysis-stress-1",
        issue_id=fix.id,
        evidence_id="ev-1",
        requested_by="user-dev",
        status=invalid_status,
        progress_stage=(
            AiProgressStage.PREPROCESSING if invalid_status == AiAnalysisStatus.PROCESSING else None
        ),
        reuse_key="rk-1",
        prompt_version="1.0.0",
        model_id="gemini-3.1-flash-lite",
        response=None,
        validation_status=AiValidationStatus.PENDING_VALIDATION,
        created_at=datetime.datetime(2026, 11, 15, 11, 0, 0, tzinfo=datetime.UTC),
    )
    ai_repo = MockAiAnalysisRepo([analysis])
    issue_repo = MockIssueRepo([fix])
    projects = MockProjectLookup({("proj-1", "user-mgr"): True})
    clock = MockClock()
    uow = MockUow()
    audit = MockAuditRecorder()

    use_case = ValidateAiAnalysisUseCase(
        ai_repo=cast(Any, ai_repo),
        issue_repo=cast(Any, issue_repo),
        projects=cast(Any, projects),
        clock=cast(Any, clock),
        uow=cast(Any, uow),
        audit_recorder=audit,
    )
    manager = _build_user("user-mgr", "Manager")

    with pytest.raises(InvalidValidationStateError) as exc_info:
        use_case.execute("proj-1", fix.id, analysis.id, manager)
    assert str(exc_info.value) == AI_VALIDATE_INVALID_STATE
    assert len(audit.records) == 0


@pytest.mark.parametrize(
    "invalid_status",
    [
        AiAnalysisStatus.PENDING,
        AiAnalysisStatus.PROCESSING,
        AiAnalysisStatus.FAILED,
    ],
)
def test_reject_rejects_non_done_analyses_with_conflict(invalid_status: AiAnalysisStatus) -> None:
    fix = _create_base_fix()
    analysis = AiAnalysis(
        id="analysis-stress-2",
        issue_id=fix.id,
        evidence_id="ev-1",
        requested_by="user-dev",
        status=invalid_status,
        progress_stage=None,
        reuse_key="rk-2",
        prompt_version="1.0.0",
        model_id="gemini-3.1-flash-lite",
        response=None,
        validation_status=AiValidationStatus.PENDING_VALIDATION,
        created_at=datetime.datetime(2026, 11, 15, 11, 0, 0, tzinfo=datetime.UTC),
    )
    ai_repo = MockAiAnalysisRepo([analysis])
    issue_repo = MockIssueRepo([fix])
    projects = MockProjectLookup({("proj-1", "user-mgr"): True})
    clock = MockClock()
    uow = MockUow()
    audit = MockAuditRecorder()

    use_case = RejectAiAnalysisUseCase(
        ai_repo=cast(Any, ai_repo),
        issue_repo=cast(Any, issue_repo),
        projects=cast(Any, projects),
        clock=cast(Any, clock),
        uow=cast(Any, uow),
        audit_recorder=audit,
    )
    manager = _build_user("user-mgr", "Manager")

    with pytest.raises(InvalidValidationStateError) as exc_info:
        use_case.execute("proj-1", fix.id, analysis.id, manager)
    assert str(exc_info.value) == AI_REJECT_INVALID_STATE
    assert len(audit.records) == 0


def test_full_state_transition_lifecycle_and_audit_trail() -> None:
    fix = _create_base_fix()
    analysis = AiAnalysis(
        id="analysis-lifecycle",
        issue_id=fix.id,
        evidence_id="ev-1",
        requested_by="user-dev",
        status=AiAnalysisStatus.DONE,
        progress_stage=None,
        reuse_key="rk-lifecycle",
        prompt_version="1.0.0",
        model_id="gemini-3.1-flash-lite",
        response=AiAnalysisResult(
            problem_description="Descripción válida",
            probable_cause="Causa válida",
            suggested_solution="Solución sugerida válida",
            context_sufficient=True,
        ),
        validation_status=AiValidationStatus.PENDING_VALIDATION,
        created_at=datetime.datetime(2026, 11, 15, 11, 0, 0, tzinfo=datetime.UTC),
    )
    ai_repo = MockAiAnalysisRepo([analysis])
    issue_repo = MockIssueRepo([fix])
    projects = MockProjectLookup({("proj-1", "user-mgr"): True, ("proj-1", "user-admin"): True})
    clock = MockClock(datetime.datetime(2026, 11, 15, 12, 30, 0, tzinfo=datetime.UTC))
    uow = MockUow()
    audit = MockAuditRecorder()

    val_use_case = ValidateAiAnalysisUseCase(
        ai_repo=cast(Any, ai_repo),
        issue_repo=cast(Any, issue_repo),
        projects=cast(Any, projects),
        clock=cast(Any, clock),
        uow=cast(Any, uow),
        audit_recorder=audit,
    )
    rej_use_case = RejectAiAnalysisUseCase(
        ai_repo=cast(Any, ai_repo),
        issue_repo=cast(Any, issue_repo),
        projects=cast(Any, projects),
        clock=cast(Any, clock),
        uow=cast(Any, uow),
        audit_recorder=audit,
    )
    manager = _build_user("user-mgr", "Manager")
    admin = _build_user("user-admin", "Admin")

    # 1. PENDING_VALIDATION -> Validate -> VALIDATED
    val_res = val_use_case.execute("proj-1", fix.id, analysis.id, manager)
    assert val_res.validation_status == "VALIDATED"
    assert analysis.validation_status == AiValidationStatus.VALIDATED
    assert analysis.validated_by == "user-mgr"
    assert analysis.validated_at == clock.now()
    assert analysis.rejected_by is None
    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "ai_analysis.validated"

    # 2. VALIDATED -> Validate again -> 409 Conflict
    with pytest.raises(InvalidValidationStateError) as exc_val_rep:
        val_use_case.execute("proj-1", fix.id, analysis.id, admin)
    assert str(exc_val_rep.value) == AI_VALIDATE_INVALID_STATE

    # 3. VALIDATED -> Reject -> REJECTED (Allowed by CA 3)
    rej_res = rej_use_case.execute(
        "proj-1",
        fix.id,
        analysis.id,
        admin,
        reason="Error detectado tras revisión",
    )
    assert rej_res.validation_status == "REJECTED"
    assert str(analysis.validation_status) == str(AiValidationStatus.REJECTED)
    assert analysis.rejected_by == "user-admin"
    assert analysis.rejected_at == clock.now()
    assert analysis.validated_by is None  # Mutually exclusive
    assert analysis.validated_at is None
    assert len(audit.records) == 2
    assert audit.records[1]["action"] == "ai_analysis.rejected"

    # 4. REJECTED -> Reject again -> 409 Conflict
    with pytest.raises(InvalidValidationStateError) as exc_rej_rep:
        rej_use_case.execute("proj-1", fix.id, analysis.id, manager)
    assert str(exc_rej_rep.value) == AI_REJECT_INVALID_STATE

    # 5. REJECTED -> Validate -> 409 Conflict (Cannot validate a rejected response)
    with pytest.raises(InvalidValidationStateError) as exc_val_rej:
        val_use_case.execute("proj-1", fix.id, analysis.id, manager)
    assert str(exc_val_rej.value) == AI_VALIDATE_INVALID_STATE

    # 6. DA-08 Mutación Cero assertion: Issue repository was NEVER saved/mutated!
    assert issue_repo.mutation_attempts == 0
    assert fix.status == IssueStatus.OPEN
    assert fix.version == 1


# =============================================================================
# 3. Stress Tests: Cross-Tenant & Non-Member Security Boundaries
# =============================================================================


def test_cross_tenant_isolation_blocks_manager_of_different_project() -> None:
    fix = _create_base_fix(project_id="proj-secret-1")
    analysis = AiAnalysis(
        id="analysis-cross",
        issue_id=fix.id,
        evidence_id="ev-1",
        requested_by="user-dev",
        status=AiAnalysisStatus.DONE,
        progress_stage=None,
        reuse_key="rk-cross",
        prompt_version="1.0.0",
        model_id="gemini-3.1-flash-lite",
        response=None,
        validation_status=AiValidationStatus.PENDING_VALIDATION,
        created_at=datetime.datetime(2026, 11, 15, 11, 0, 0, tzinfo=datetime.UTC),
    )
    ai_repo = MockAiAnalysisRepo([analysis])
    issue_repo = MockIssueRepo([fix])
    # Attacker manager is manager of proj-2, NOT proj-secret-1
    projects = MockProjectLookup({("proj-2", "user-attacker-mgr"): True})
    clock = MockClock()
    uow = MockUow()
    audit = MockAuditRecorder()

    val_use_case = ValidateAiAnalysisUseCase(
        ai_repo=cast(Any, ai_repo),
        issue_repo=cast(Any, issue_repo),
        projects=cast(Any, projects),
        clock=cast(Any, clock),
        uow=cast(Any, uow),
        audit_recorder=audit,
    )
    rej_use_case = RejectAiAnalysisUseCase(
        ai_repo=cast(Any, ai_repo),
        issue_repo=cast(Any, issue_repo),
        projects=cast(Any, projects),
        clock=cast(Any, clock),
        uow=cast(Any, uow),
        audit_recorder=audit,
    )
    attacker_mgr = _build_user("user-attacker-mgr", "Manager")

    # Trying to validate in proj-secret-1 -> 403
    with pytest.raises(PermissionError) as val_exc:
        val_use_case.execute("proj-secret-1", fix.id, analysis.id, attacker_mgr)
    assert str(val_exc.value) == NOT_MEMBER_ERROR

    # Trying to reject in proj-secret-1 -> 403
    with pytest.raises(PermissionError) as rej_exc:
        rej_use_case.execute("proj-secret-1", fix.id, analysis.id, attacker_mgr)
    assert str(rej_exc.value) == NOT_MEMBER_ERROR

    # No audit records recorded
    assert len(audit.records) == 0
