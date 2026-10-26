"""Sprint application DTOs."""

from datetime import date

from pydantic import BaseModel, Field

from app.modules.sprints.domain.entities import SprintStatus


class CreateSprintCommand(BaseModel):
    name: str
    goal: str | None = None
    start_date: date
    end_date: date


class SprintSummaryDTO(BaseModel):
    id: str
    name: str
    goal: str | None
    start_date: date
    end_date: date
    status: SprintStatus
    story_count: int = 0
    total_points: int = 0


class CreateSprintResponse(BaseModel):
    id: str
    message: str
    status: SprintStatus


class AssignStoryToSprintCommand(BaseModel):
    sprint_id: str


class AssignStoryToSprintResponse(BaseModel):
    message: str
    sprint_total_points: int


class StartSprintResponse(BaseModel):
    message: str
    status: SprintStatus


class CurrentSprintMetricsDTO(BaseModel):
    id: str
    name: str
    goal: str | None
    days_remaining: int
    total_points: int
    completed_points: int
    pending_points: int
    progress_percentage: float


class CurrentSprintResponse(BaseModel):
    sprint: CurrentSprintMetricsDTO | None = None
    message: str | None = None


class SprintListResponse(BaseModel):
    items: list[SprintSummaryDTO]


class MessageResponse(BaseModel):
    message: str = Field(default="")
