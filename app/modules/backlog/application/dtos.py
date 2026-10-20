"""DTOs for backlog API."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.backlog.domain.entities import MoscowPriority, StoryTaskType


class MessageResponse(BaseModel):
    message: str


class EpicDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    description: str
    color: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class UserStoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    epic_id: str
    project_id: str
    title: str
    user_role: str
    reason: str
    acceptance_criteria: str
    moscow_priority: MoscowPriority
    story_points: int | None
    sprint_id: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class StoryTaskDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_story_id: str
    project_id: str
    name: str
    task_type: StoryTaskType
    notes: str
    status: str
    assignee_id: str | None
    estimated_hours: Decimal | None
    created_at: datetime
    updated_at: datetime


class EpicWithStoriesDTO(BaseModel):
    epic: EpicDTO
    stories: list[UserStoryDTO]


class UserStoryWithTasksDTO(BaseModel):
    story: UserStoryDTO
    tasks: list[StoryTaskDTO]


class BacklogTreeDTO(BaseModel):
    epics: list[EpicWithStoriesDTO]
    tasks_by_story: dict[str, list[StoryTaskDTO]]


class CreateEpicCommand(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=2000)
    color: str | None = Field(default=None, max_length=7)


class UpdateEpicCommand(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=2000)
    color: str | None = Field(default=None, max_length=7)


class CreateUserStoryCommand(BaseModel):
    title: str = Field(max_length=200)
    user_role: str = Field(max_length=200)
    reason: str = Field(max_length=2000)
    acceptance_criteria: str = Field(default="", max_length=8000)
    moscow_priority: MoscowPriority = MoscowPriority.MUST_HAVE
    epic_id: str | None = Field(default=None, max_length=36)


class UpdateUserStoryCommand(BaseModel):
    title: str = Field(max_length=200)
    user_role: str = Field(max_length=200)
    reason: str = Field(max_length=2000)
    acceptance_criteria: str = Field(default="", max_length=8000)
    moscow_priority: MoscowPriority
    epic_id: str = Field(max_length=36)


class AssignStoryPointsCommand(BaseModel):
    story_points: int | None = None


class CreateStoryTaskCommand(BaseModel):
    name: str = Field(max_length=200)
    task_type: StoryTaskType
    notes: str = Field(default="", max_length=2000)


class UpdateStoryTaskCommand(BaseModel):
    name: str = Field(max_length=200)
    task_type: StoryTaskType
    notes: str = Field(default="", max_length=2000)


class AssignStoryTaskCommand(BaseModel):
    assignee_id: str | None = Field(default=None, max_length=36)


class UpdateEstimatedHoursCommand(BaseModel):
    estimated_hours: Decimal | None = None
