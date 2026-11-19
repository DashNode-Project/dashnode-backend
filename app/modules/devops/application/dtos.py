"""Pydantic DTOs for DevOps practices API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRefDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class PipelineStageDTO(BaseModel):
    order: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    tool: str = Field(min_length=1, max_length=200)
    commands: str = Field(min_length=1)
    trigger_event: str = Field(min_length=1, max_length=200)
    is_required: bool
    notes: str | None = None


class EnvironmentDTO(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=500)
    branch: str = Field(min_length=1, max_length=200)
    deploy_strategy: str = Field(min_length=1, max_length=200)
    requires_approval: bool
    notes: str | None = None


class UpsertDevOpsProfileRequest(BaseModel):
    repository_url: str | None = None
    ci_cd_provider: str | None = Field(default=None, max_length=100)
    branching_strategy: str | None = Field(default=None, max_length=100)
    branching_rules_md: str | None = None
    pipeline_stages: list[PipelineStageDTO] = Field(default_factory=list)
    environments: list[EnvironmentDTO] = Field(default_factory=list)
    quality_gates_md: str | None = None
    deployment_runbook_md: str | None = None
    rollback_observability_md: str | None = None
    change_summary: str = Field(min_length=1, max_length=255)


class DevOpsProfileResponse(BaseModel):
    project_id: str
    is_configured: bool
    can_edit: bool
    repository_url: str | None = None
    ci_cd_provider: str | None = None
    branching_strategy: str | None = None
    branching_rules_md: str | None = None
    pipeline_stages: list[PipelineStageDTO] = Field(default_factory=list)
    environments: list[EnvironmentDTO] = Field(default_factory=list)
    quality_gates_md: str | None = None
    deployment_runbook_md: str | None = None
    rollback_observability_md: str | None = None
    updated_by: UserRefDTO | None = None
    updated_at: datetime | None = None


class DevOpsRevisionDTO(BaseModel):
    id: str
    change_summary: str
    changed_by: UserRefDTO | None = None
    created_at: datetime
    snapshot: dict[str, object]


class DevOpsRevisionListResponse(BaseModel):
    items: list[DevOpsRevisionDTO]
    limit: int
    offset: int
