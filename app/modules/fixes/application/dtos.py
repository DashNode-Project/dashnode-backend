"""DTOs for EP-11 Issues and Evidences.

@sad AD-09
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

from pydantic import BaseModel, ConfigDict, Field


class CreateIssueCommand(BaseModel):
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
    resolution_note: str | None = None
    resolved_at: str | None = None
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
    resolution_note: str | None = None
    resolved_at: str | None = None
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


class EvidenceOperationResponse(BaseModel):
    message: str
    evidence: EvidenceDTO
