"""DTOs for EP-11 Issues and Evidences.

@sad AD-09
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateIssueCommand(BaseModel):
    title: str = ""
    description: str | None = None
    severity: str = ""
    type: str = ""
    idempotency_key: str | None = None


class AssignIssueCommand(BaseModel):
    assignee_id: str | None = None
    version: int | None = None


class ResolveIssueCommand(BaseModel):
    resolution_note: str = ""
    task_status: str | None = None
    version: int | None = None


class CloseIssueCommand(BaseModel):
    task_status: str | None = None
    version: int | None = None


class ReportTaskFixCommand(BaseModel):
    title: str = ""
    description: str | None = None
    severity: str = ""
    type: str = ""
    idempotency_key: str | None = None


class EvidenceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    fix_id: str
    title: str | None = None
    file_name: str
    file_type: str
    mime_type: str
    file_size: int
    download_url: str
    thumbnail_url: str | None = None
    duration_seconds: float | None = None
    uploaded_by: str
    uploaded_by_name: str
    created_at: str


class IssueDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    description: str | None = None
    severity: str
    type: str
    status: str
    reporter_id: str
    reporter_name: str
    assignee_id: str | None = None
    assignee_name: str | None = None
    task_id: str | None = None
    task_name: str | None = None
    task_status: str | None = None
    task_previous_status: str | None = None
    resolution_note: str | None = None
    resolved_by: str | None = None
    resolved_by_name: str | None = None
    resolved_at: str | None = None
    version: int = 1
    created_at: str
    updated_at: str
    evidences_count: int = 0


class AIAnalysisSummaryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_id: str | None = None
    fix_id: str | None = None
    diagnosis: str | None = None
    recommendation: str | None = None
    observations: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    suggested_steps: list[str] = Field(default_factory=list)


class IssueDetailDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    description: str | None = None
    severity: str
    type: str
    status: str
    reporter_id: str
    reporter_name: str
    assignee_id: str | None = None
    assignee_name: str | None = None
    task_id: str | None = None
    task_name: str | None = None
    task_status: str | None = None
    task_previous_status: str | None = None
    other_open_issues_count: int = 0
    resolution_note: str | None = None
    resolved_by: str | None = None
    resolved_by_name: str | None = None
    resolved_at: str | None = None
    version: int = 1
    created_at: str
    updated_at: str
    evidences_count: int = 0
    evidences: list[EvidenceDTO] = Field(default_factory=list)
    ai_analyses: list[AIAnalysisSummaryDTO] = Field(default_factory=list)


class IssueListResponse(BaseModel):
    items: list[IssueDTO]
    next_cursor: str | None = None
    total: int


class IssueOperationResponse(BaseModel):
    message: str
    issue: IssueDTO
    task_unlinked: bool = False
    task_id: str | None = None
    task_status: str | None = None
    task_message: str | None = None


class EvidenceOperationResponse(BaseModel):
    message: str
    evidence: EvidenceDTO


# EP-12 AI visual evidence analysis DTOs (HU_DN_07_106 .. HU_DN_07_110)


class RequestAiAnalysisCommand(BaseModel):
    evidence_id: str | None = None
    user_confirmed_no_sensitive_data: bool = False
    confirmed_no_sensitive_data: bool | None = None
    force_new: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_confirmation(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if (
                "confirmed_no_sensitive_data" in values
                and "user_confirmed_no_sensitive_data" not in values
            ):
                values["user_confirmed_no_sensitive_data"] = values["confirmed_no_sensitive_data"]
            elif (
                "user_confirmed_no_sensitive_data" in values
                and "confirmed_no_sensitive_data" not in values
            ):
                values["confirmed_no_sensitive_data"] = values["user_confirmed_no_sensitive_data"]
        return values


class AiAnalysisResultDTO(BaseModel):
    problem_description: str
    probable_cause: str
    suggested_solution: str | None = None
    context_sufficient: bool = True


class RequestAiAnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    message: str
    reused: bool = False


class AiAnalysisStatusResponse(BaseModel):
    analysis_id: str
    status: str
    progress_stage: str | None = None
    validation_status: str = "PENDING_VALIDATION"
    requires_human_validation: bool = True
    validated_by_name: str | None = None
    validated_at: str | None = None
    rejected_by_name: str | None = None
    rejected_at: str | None = None
    result: AiAnalysisResultDTO | None = None
    error_code: str | None = None
    message: str | None = None
    retryable: bool = False
    created_at: str | None = None


class AiAnalysisRequesterDTO(BaseModel):
    id: str
    name: str


class AiAnalysisListItemDTO(BaseModel):
    id: str
    requested_by: AiAnalysisRequesterDTO
    created_at: str
    validation_status: str
    summary: str
    requires_human_validation: bool = True
    validated_by_name: str | None = None
    validated_at: str | None = None
    rejected_by_name: str | None = None
    rejected_at: str | None = None
    result: AiAnalysisResultDTO | None = None
    evidence_id: str | None = None


class AiAnalysisListResponse(BaseModel):
    items: list[AiAnalysisListItemDTO]
    next_cursor: str | None = None


# EP-12 Human validation DTOs (HU_DN_07_111 .. HU_DN_07_113)


class ValidateAiAnalysisResponse(BaseModel):
    message: str
    validation_status: str


class RejectAiAnalysisRequest(BaseModel):
    reason: str | None = None


class RejectAiAnalysisResponse(BaseModel):
    message: str
    validation_status: str
