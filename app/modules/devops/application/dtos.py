"""DevOps API DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TriggeredByDTO(BaseModel):
    id: str
    name: str


class PipelineStageDTO(BaseModel):
    stage: str
    status: str
    duration_seconds: int
    started_at: datetime
    finished_at: datetime
    skip_reason: str | None = None


class LatestPipelineResponse(BaseModel):
    run_id: str | None
    is_simulated: bool = True
    trigger: str | None = None
    triggered_by: TriggeredByDTO | None = None
    created_at: datetime | None = None
    status: str | None = None
    computed_at: datetime
    stages: list[PipelineStageDTO]


class TriggerPipelineResponse(BaseModel):
    run_id: str
    created_at: datetime
