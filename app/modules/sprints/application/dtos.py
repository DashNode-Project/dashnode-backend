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


class BurndownPointDTO(BaseModel):
    date: str
    points: int


class SprintBurndownResponse(BaseModel):
    ideal_line: list[BurndownPointDTO]
    actual_line: list[BurndownPointDTO]


class CloseSprintCommand(BaseModel):
    incomplete_stories_destination: str | None = None
    incomplete_stories_action: str | None = None
    target_sprint_id: str | None = None


class CloseSprintResponse(BaseModel):
    message: str
    status: SprintStatus
    moved_stories_count: int = 0


class SprintHistoryItemDTO(BaseModel):
    sprint_id: str
    name: str
    start_date: date
    end_date: date
    committed_points: int
    completed_points: int
    fulfillment_percentage: float


class SprintHistoryResponse(BaseModel):
    history: list[SprintHistoryItemDTO]
    message: str | None = None
