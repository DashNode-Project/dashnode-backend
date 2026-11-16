"""Application use cases for EP-12 AI visual evidence analysis.

@sad Anexo D, DA-01, DA-06, DA-07, DA-08
@origin [User Stories HU_DN_07_106 .. HU_DN_07_110]
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import cast

from app.modules.ai_metrics.application.interaction_registry import (
    SOURCE_ISSUE_ANALYSIS,
    InteractionRegistry,
    StepRecord,
)
from app.modules.fixes.application.dtos import (
    AiAnalysisListItemDTO,
    AiAnalysisListResponse,
    AiAnalysisRequesterDTO,
    AiAnalysisResultDTO,
    AiAnalysisStatusResponse,
    RejectAiAnalysisResponse,
    RequestAiAnalysisCommand,
    RequestAiAnalysisResponse,
    ValidateAiAnalysisResponse,
)
from app.modules.fixes.application.vision_pipeline import (
    PROMPT_VERSION,
    VisionPipelineError,
)
from app.modules.fixes.domain.entities import (
    AiAnalysis,
    AiAnalysisStatus,
    AiProgressStage,
    AiValidationStatus,
    EvidenceType,
)
from app.modules.fixes.domain.messages import (
    AI_ANALYSIS_DELETED,
    AI_ANALYSIS_NOT_FOUND,
    AI_ANALYSIS_REQUESTED,
    AI_ANALYSIS_REUSED,
    AI_CONFIRMATION_REQUIRED,
    AI_DELETE_FORBIDDEN,
    AI_DELETE_PROCESSING_FORBIDDEN,
    AI_OUTPUT_INVALID,
    AI_PROVIDER_ERROR,
    AI_QUOTA_EXHAUSTED,
    AI_REJECT_FORBIDDEN,
    AI_REJECT_INVALID_STATE,
    AI_REJECT_SUCCESS,
    AI_TIMEOUT,
    AI_UNSUPPORTED_FORMAT,
    AI_VALIDATE_FORBIDDEN,
    AI_VALIDATE_INVALID_STATE,
    AI_VALIDATE_SUCCESS,
    DAILY_LIMIT_REACHED,
    EVIDENCE_LOAD_ERROR,
    ISSUE_NOT_FOUND,
    NO_EVIDENCE_FOR_ANALYSIS,
    NOT_MEMBER_ERROR,
)
from app.modules.fixes.domain.ports import (
    AiAnalysisRepository,
    AiQuotaLookup,
    AuditLogRecorder,
    EvidenceFileStorage,
    EvidenceRepository,
    IssueRepository,
    ProjectLookupPort,
    UserDisplayLookupPort,
    VisionAnalysisProvider,
)
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)

ERROR_CODE_MESSAGES: dict[str, str] = {
    "EVIDENCE_LOAD_ERROR": EVIDENCE_LOAD_ERROR,
    "UNSUPPORTED_FORMAT": AI_UNSUPPORTED_FORMAT,
    "AI_PROVIDER_ERROR": AI_PROVIDER_ERROR,
    "AI_OUTPUT_INVALID": AI_OUTPUT_INVALID,
    "AI_TIMEOUT": AI_TIMEOUT,
    "AI_QUOTA_EXHAUSTED": AI_QUOTA_EXHAUSTED,
    "DAILY_LIMIT_REACHED": DAILY_LIMIT_REACHED,
    "NO_EVIDENCE": NO_EVIDENCE_FOR_ANALYSIS,
}


class DailyLimitReachedError(Exception):
    """Raised when the user daily limit for AI analysis is reached."""


class InvalidValidationStateError(Exception):
    """Raised when an AI analysis is in an invalid state for validation or rejection."""


class RequestAiAnalysisUseCase:
    """HU_DN_07_106 & HU_DN_07_110: Request AI visual analysis of issue evidence."""

    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        issue_repo: IssueRepository,
        evidence_repo: EvidenceRepository,
        storage: EvidenceFileStorage,
        projects: ProjectLookupPort,
        quota: AiQuotaLookup,
        vision_provider: VisionAnalysisProvider,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        background_executor: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self._ai_repo = ai_repo
        self._issue_repo = issue_repo
        self._evidence_repo = evidence_repo
        self._storage = storage
        self._projects = projects
        self._quota = quota
        self._vision_provider = vision_provider
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._background_executor = background_executor

    def execute(
        self,
        project_id: str,
        issue_id: str,
        cmd: RequestAiAnalysisCommand,
        actor: CurrentUser,
    ) -> RequestAiAnalysisResponse:
        # Authorization check
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        # Mandatory confirmation checkbox
        is_confirmed = cmd.user_confirmed_no_sensitive_data or bool(cmd.confirmed_no_sensitive_data)
        if not is_confirmed:
            raise ValueError(AI_CONFIRMATION_REQUIRED)

        # Issue validation
        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        # Evidence validation
        if cmd.evidence_id:
            evidence = self._evidence_repo.get_by_id(cmd.evidence_id)
            if evidence is None or evidence.fix_id != issue_id:
                raise ValueError(NO_EVIDENCE_FOR_ANALYSIS)
        else:
            evidences = self._evidence_repo.list_by_issue(issue_id)
            if not evidences:
                raise ValueError(NO_EVIDENCE_FOR_ANALYSIS)
            visual_evs = [
                e for e in evidences if e.file_type in (EvidenceType.IMAGE, EvidenceType.VIDEO)
            ]
            if not visual_evs:
                raise ValueError(AI_UNSUPPORTED_FORMAT)
            evidence = visual_evs[0]

        # Evidence format validation (only IMAGE and VIDEO supported in v1)
        if evidence.file_type not in (EvidenceType.IMAGE, EvidenceType.VIDEO):
            raise ValueError(AI_UNSUPPORTED_FORMAT)

        # Calculate reuse key: SHA-256(evidence.sha256 || prompt_version)
        reuse_key = hashlib.sha256(f"{evidence.sha256_hash}:{PROMPT_VERSION}".encode()).hexdigest()

        # Reusability check (DA-06)
        if not cmd.force_new:
            existing = self._ai_repo.find_active_by_reuse_key(reuse_key)
            if existing is not None and existing.status == AiAnalysisStatus.DONE:
                return RequestAiAnalysisResponse(
                    analysis_id=existing.id,
                    status=existing.status.value,
                    message=AI_ANALYSIS_REUSED,
                    reused=True,
                )

        # Pre-check daily quota (read-only pre-check DA-07)
        if not self._quota.check_user_limit(actor.id):
            raise DailyLimitReachedError(DAILY_LIMIT_REACHED)

        # Enqueue new analysis record with status PENDING
        analysis_id = self._id_gen.generate()
        now = self._clock.now()
        analysis = AiAnalysis(
            id=analysis_id,
            issue_id=issue_id,
            evidence_id=evidence.id,
            requested_by=actor.id,
            status=AiAnalysisStatus.PENDING,
            progress_stage=AiProgressStage.PREPROCESSING,
            reuse_key=reuse_key,
            prompt_version=PROMPT_VERSION,
            model_id="gemini-3.1-flash-lite",
            response=None,
            validation_status=AiValidationStatus.PENDING_VALIDATION,
            created_at=now,
        )
        self._ai_repo.save(analysis)
        self._uow.commit()

        # Define the worker job
        def run_worker() -> None:
            self._process_analysis(analysis_id, actor.id)

        # Dispatch async background worker if executor provided, else run synchronously
        if self._background_executor:
            self._background_executor(run_worker)
        else:
            run_worker()

        return RequestAiAnalysisResponse(
            analysis_id=analysis_id,
            status=AiAnalysisStatus.PENDING.value,
            message=AI_ANALYSIS_REQUESTED,
            reused=False,
        )

    def _process_analysis(self, analysis_id: str, actor_id: str) -> None:
        analysis = self._ai_repo.get_by_id(analysis_id)
        if analysis is None:
            return

        evidence = self._evidence_repo.get_by_id(analysis.evidence_id)
        issue = self._issue_repo.get_by_id(analysis.issue_id)
        registry = InteractionRegistry(cast(SqlAlchemyUnitOfWork, self._uow).session)
        interaction_id: str | None = None
        if evidence is None or issue is None:
            analysis.status = AiAnalysisStatus.FAILED
            analysis.error_code = "EVIDENCE_LOAD_ERROR"
            self._ai_repo.save(analysis)
            self._uow.commit()
            return

        interaction_id = registry.start_pending(
            user_id=actor_id,
            project_id=issue.project_id,
            source=SOURCE_ISSUE_ANALYSIS,
            request_text=f"issue:{analysis.issue_id}",
        )
        self._uow.commit()

        try:
            # Stage: PROCESSING / PREPROCESSING
            analysis.status = AiAnalysisStatus.PROCESSING
            analysis.progress_stage = AiProgressStage.PREPROCESSING
            self._ai_repo.save(analysis)
            self._uow.commit()

            # Load file bytes
            try:
                evidence_data = self._storage.read_file(evidence.storage_path)
            except Exception as exc:
                logger.error("Failed to read evidence file from storage: %s", exc)
                analysis.status = AiAnalysisStatus.FAILED
                analysis.error_code = "EVIDENCE_LOAD_ERROR"
                self._ai_repo.save(analysis)
                if interaction_id:
                    registry.complete_error(interaction_id, error_code="EVIDENCE_LOAD_ERROR")
                    registry.link_analysis(analysis_id, interaction_id)
                self._uow.commit()
                return

            # Stage: UPLOADING / ANALYZING
            analysis.progress_stage = AiProgressStage.ANALYZING
            self._ai_repo.save(analysis)
            self._uow.commit()

            # Atomic quota consumption upon effective provider dispatch (DA-07)
            self._quota.consume_quota(actor_id)

            # Invoke provider
            issue_context = {
                "title": issue.title,
                "description": issue.description or "",
                "severity": issue.severity.value,
                "type": issue.type.value,
            }
            result, in_tokens, out_tokens, latency, model_id = self._vision_provider.analyze(
                evidence_data=evidence_data,
                evidence_type=evidence.file_type.value,
                evidence_title=evidence.title,
                issue_context=issue_context,
            )

            # Persist successful analysis
            analysis.status = AiAnalysisStatus.DONE
            analysis.progress_stage = None
            analysis.response = result
            analysis.input_tokens = in_tokens
            analysis.output_tokens = out_tokens
            analysis.latency_ms = latency
            analysis.model_id = model_id
            analysis.error_code = None
            self._ai_repo.save(analysis)
            if interaction_id:
                registry.record_step(
                    interaction_id,
                    1,
                    StepRecord(
                        step_type="VISION_ANALYSIS",
                        status="SUCCESS",
                        model_id=model_id,
                        input_tokens=in_tokens or 0,
                        output_tokens=out_tokens or 0,
                        latency_ms=latency or 0,
                    ),
                )
                registry.complete_success(
                    interaction_id,
                    response_text=result.problem_description[:2000] if result else None,
                    model_id=model_id,
                    input_tokens=in_tokens or 0,
                    output_tokens=out_tokens or 0,
                    total_latency_ms=latency or 0,
                )
                registry.link_analysis(analysis_id, interaction_id)
            self._uow.commit()

        except VisionPipelineError as err:
            logger.warning("Vision pipeline failed with code %s: %s", err.error_code, err)
            analysis.status = AiAnalysisStatus.FAILED
            analysis.progress_stage = None
            analysis.error_code = err.error_code
            self._ai_repo.save(analysis)
            if interaction_id:
                registry.complete_error(interaction_id, error_code=err.error_code)
                registry.link_analysis(analysis_id, interaction_id)
            self._uow.commit()
        except Exception as exc:
            logger.exception("Unexpected error in vision worker: %s", exc)
            analysis.status = AiAnalysisStatus.FAILED
            analysis.progress_stage = None
            analysis.error_code = "AI_PROVIDER_ERROR"
            self._ai_repo.save(analysis)
            if interaction_id:
                registry.complete_error(interaction_id, error_code="AI_PROVIDER_ERROR")
                registry.link_analysis(analysis_id, interaction_id)
            self._uow.commit()


class GetAiAnalysisStatusUseCase:
    """HU_DN_07_106 & HU_DN_07_107 & HU_DN_07_110 & HU_DN_07_113: Query analysis status & result."""

    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        issue_repo: IssueRepository,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort | None = None,
    ) -> None:
        self._ai_repo = ai_repo
        self._issue_repo = issue_repo
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        issue_id: str,
        analysis_id: str,
        actor: CurrentUser,
    ) -> AiAnalysisStatusResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        analysis = self._ai_repo.get_by_id(analysis_id)
        if analysis is None or analysis.issue_id != issue_id:
            raise LookupError(AI_ANALYSIS_NOT_FOUND)

        result_dto: AiAnalysisResultDTO | None = None
        if analysis.response:
            result_dto = AiAnalysisResultDTO(
                problem_description=analysis.response.problem_description,
                probable_cause=analysis.response.probable_cause,
                suggested_solution=(
                    analysis.response.suggested_solution
                    if analysis.response.context_sufficient
                    else None
                ),
                context_sufficient=analysis.response.context_sufficient,
            )

        err_msg = ERROR_CODE_MESSAGES.get(analysis.error_code or "", "")

        # HU_DN_07_113: requires_human_validation calculated on server
        requires_human_val = analysis.validation_status != AiValidationStatus.VALIDATED

        val_name: str | None = None
        if analysis.validated_by and self._users:
            val_disp = self._users.get_user_display(analysis.validated_by)
            val_name = val_disp[0] if val_disp else None

        rej_name: str | None = None
        if analysis.rejected_by and self._users:
            rej_disp = self._users.get_user_display(analysis.rejected_by)
            rej_name = rej_disp[0] if rej_disp else None

        return AiAnalysisStatusResponse(
            analysis_id=analysis.id,
            status=analysis.status.value,
            progress_stage=analysis.progress_stage.value if analysis.progress_stage else None,
            validation_status=analysis.validation_status.value,
            requires_human_validation=requires_human_val,
            validated_by_name=val_name,
            validated_at=analysis.validated_at.isoformat() if analysis.validated_at else None,
            rejected_by_name=rej_name,
            rejected_at=analysis.rejected_at.isoformat() if analysis.rejected_at else None,
            result=result_dto,
            error_code=analysis.error_code,
            message=err_msg if analysis.status == AiAnalysisStatus.FAILED else None,
            retryable=analysis.status == AiAnalysisStatus.FAILED,
            created_at=analysis.created_at.isoformat(),
        )


class ListAiAnalysesUseCase:
    """HU_DN_07_108 & HU_DN_07_113: Query stored AI responses for an issue."""

    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        issue_repo: IssueRepository,
        projects: ProjectLookupPort,
        users: UserDisplayLookupPort,
    ) -> None:
        self._ai_repo = ai_repo
        self._issue_repo = issue_repo
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        issue_id: str,
        actor: CurrentUser,
        limit: int = 20,
        cursor: str | None = None,
    ) -> AiAnalysisListResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        items, next_cursor = self._ai_repo.list_by_issue(issue_id, limit=limit, cursor=cursor)

        # Batch resolve user names via display lookup
        user_ids = {item.requested_by for item in items}
        user_ids.update(item.validated_by for item in items if item.validated_by)
        user_ids.update(item.rejected_by for item in items if item.rejected_by)
        user_map: dict[str, str] = {}
        for uid in user_ids:
            disp = self._users.get_user_display(uid)
            user_map[uid] = disp[0] if disp else "Usuario"

        list_dtos: list[AiAnalysisListItemDTO] = []
        for item in items:
            summary = ""
            result_dto: AiAnalysisResultDTO | None = None
            if item.response:
                summary = item.response.problem_description[:120]
                result_dto = AiAnalysisResultDTO(
                    problem_description=item.response.problem_description,
                    probable_cause=item.response.probable_cause,
                    suggested_solution=(
                        item.response.suggested_solution
                        if item.response.context_sufficient
                        else None
                    ),
                    context_sufficient=item.response.context_sufficient,
                )
            elif item.error_code:
                summary = ERROR_CODE_MESSAGES.get(item.error_code, item.error_code)

            requires_human_val = item.validation_status != AiValidationStatus.VALIDATED

            list_dtos.append(
                AiAnalysisListItemDTO(
                    id=item.id,
                    requested_by=AiAnalysisRequesterDTO(
                        id=item.requested_by,
                        name=user_map.get(item.requested_by, "Usuario"),
                    ),
                    created_at=item.created_at.isoformat(),
                    validation_status=item.validation_status.value,
                    summary=summary,
                    requires_human_validation=requires_human_val,
                    validated_by_name=(
                        user_map.get(item.validated_by) if item.validated_by else None
                    ),
                    validated_at=item.validated_at.isoformat() if item.validated_at else None,
                    rejected_by_name=(user_map.get(item.rejected_by) if item.rejected_by else None),
                    rejected_at=item.rejected_at.isoformat() if item.rejected_at else None,
                    result=result_dto,
                    evidence_id=item.evidence_id,
                )
            )

        return AiAnalysisListResponse(items=list_dtos, next_cursor=next_cursor)


class DeleteAiAnalysisUseCase:
    """HU_DN_07_109: Soft delete an AI response with role checking and audit log."""

    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        issue_repo: IssueRepository,
        projects: ProjectLookupPort,
        audit_recorder: AuditLogRecorder,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._ai_repo = ai_repo
        self._issue_repo = issue_repo
        self._projects = projects
        self._audit_recorder = audit_recorder
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        project_id: str,
        issue_id: str,
        analysis_id: str,
        actor: CurrentUser,
    ) -> dict[str, str]:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        analysis = self._ai_repo.get_by_id(analysis_id)
        if analysis is None or analysis.issue_id != issue_id:
            raise LookupError(AI_ANALYSIS_NOT_FOUND)

        # Block deletion while processing
        if analysis.status == AiAnalysisStatus.PROCESSING:
            raise ValueError(AI_DELETE_PROCESSING_FORBIDDEN)

        # RBAC Check: Admin, Manager or original requester only
        is_admin_or_mgr = actor.role.lower() in ("admin", "administrator", "manager")
        is_requester = analysis.requested_by == actor.id
        if not (is_admin_or_mgr or is_requester):
            raise PermissionError(AI_DELETE_FORBIDDEN)

        now = self._clock.now()
        success = self._ai_repo.soft_delete(analysis_id, actor.id, now)
        if not success:
            raise LookupError(AI_ANALYSIS_NOT_FOUND)

        # Audit trail (RNF-SEG-07)
        self._audit_recorder.record(
            user_id=actor.id,
            action="ai_analysis.deleted",
            resource_type="ai_analysis",
            resource_id=analysis_id,
            created_at=now,
        )
        self._uow.commit()

        return {"message": AI_ANALYSIS_DELETED}


class ValidateAiAnalysisUseCase:
    """HU_DN_07_111: Validate an AI response before taking action upon it."""

    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        issue_repo: IssueRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
        audit_recorder: AuditLogRecorder | None = None,
    ) -> None:
        self._ai_repo = ai_repo
        self._issue_repo = issue_repo
        self._projects = projects
        self._clock = clock
        self._uow = uow
        self._audit_recorder = audit_recorder

    def execute(
        self,
        project_id: str,
        issue_id: str,
        analysis_id: str,
        actor: CurrentUser,
    ) -> ValidateAiAnalysisResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        # RBAC Check (CA 4): Only Admin or Manager can validate AI responses
        is_admin_or_mgr = actor.role.lower() in ("admin", "administrator", "manager")
        if not is_admin_or_mgr:
            raise PermissionError(AI_VALIDATE_FORBIDDEN)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        analysis = self._ai_repo.get_by_id(analysis_id)
        if analysis is None or analysis.issue_id != issue_id:
            raise LookupError(AI_ANALYSIS_NOT_FOUND)

        # Precondition (CA 3): Only completed analyses in pending validation state can be validated
        if (
            analysis.status != AiAnalysisStatus.DONE
            or analysis.validation_status != AiValidationStatus.PENDING_VALIDATION
        ):
            raise InvalidValidationStateError(AI_VALIDATE_INVALID_STATE)

        now = self._clock.now()
        analysis.validation_status = AiValidationStatus.VALIDATED
        analysis.validated_by = actor.id
        analysis.validated_at = now
        analysis.rejected_by = None
        analysis.rejected_at = None

        # DA-08: Zero mutations on fixes or tasks; only updates ai_analyses
        self._ai_repo.save(analysis)

        if self._audit_recorder:
            self._audit_recorder.record(
                user_id=actor.id,
                action="ai_analysis.validated",
                resource_type="ai_analysis",
                resource_id=analysis_id,
                created_at=now,
            )

        self._uow.commit()

        return ValidateAiAnalysisResponse(
            message=AI_VALIDATE_SUCCESS,
            validation_status="VALIDATED",
        )


class RejectAiAnalysisUseCase:
    """HU_DN_07_112: Reject an AI response."""

    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        issue_repo: IssueRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
        audit_recorder: AuditLogRecorder | None = None,
    ) -> None:
        self._ai_repo = ai_repo
        self._issue_repo = issue_repo
        self._projects = projects
        self._clock = clock
        self._uow = uow
        self._audit_recorder = audit_recorder

    def execute(
        self,
        project_id: str,
        issue_id: str,
        analysis_id: str,
        actor: CurrentUser,
        reason: str | None = None,
    ) -> RejectAiAnalysisResponse:
        if not self._projects.is_active_member(project_id, actor.id):
            raise PermissionError(NOT_MEMBER_ERROR)

        # RBAC Check (CA 4): Only Admin or Manager can reject AI responses
        is_admin_or_mgr = actor.role.lower() in ("admin", "administrator", "manager")
        if not is_admin_or_mgr:
            raise PermissionError(AI_REJECT_FORBIDDEN)

        issue = self._issue_repo.get_by_id(issue_id)
        if issue is None or issue.project_id != project_id:
            raise LookupError(ISSUE_NOT_FOUND)

        analysis = self._ai_repo.get_by_id(analysis_id)
        if analysis is None or analysis.issue_id != issue_id:
            raise LookupError(AI_ANALYSIS_NOT_FOUND)

        # Precondition (CA 3): Can reject from PENDING_VALIDATION or VALIDATED.
        # If already REJECTED, return 409 Conflict: "La respuesta ya fue rechazada."
        if analysis.validation_status == AiValidationStatus.REJECTED:
            raise InvalidValidationStateError(AI_REJECT_INVALID_STATE)
        if analysis.status != AiAnalysisStatus.DONE or analysis.validation_status not in (
            AiValidationStatus.PENDING_VALIDATION,
            AiValidationStatus.VALIDATED,
        ):
            raise InvalidValidationStateError(AI_REJECT_INVALID_STATE)

        now = self._clock.now()
        analysis.validation_status = AiValidationStatus.REJECTED
        analysis.rejected_by = actor.id
        analysis.rejected_at = now
        analysis.validated_by = None
        analysis.validated_at = None

        # DA-08: Zero mutations on fixes or tasks; only updates ai_analyses
        self._ai_repo.save(analysis)

        if self._audit_recorder:
            self._audit_recorder.record(
                user_id=actor.id,
                action="ai_analysis.rejected",
                resource_type="ai_analysis",
                resource_id=analysis_id,
                created_at=now,
            )

        self._uow.commit()

        return RejectAiAnalysisResponse(
            message=AI_REJECT_SUCCESS,
            validation_status="REJECTED",
        )
