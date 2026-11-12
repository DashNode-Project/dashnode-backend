"""Kanban DTOs (EP-08)."""

from datetime import date

from pydantic import BaseModel, Field


class KanbanCardDTO(BaseModel):
    id: str
    title: str
    task_type: str
    status: str
    assignee_id: str | None = None
    assignee_name: str | None = None
    assignee_avatar_url: str | None = None
    user_story_id: str
    user_story_label: str = ""
    user_story_title: str = ""
    estimated_hours: float = 0.0
    logged_hours: float = 0.0
    is_blocked: bool = False
    blocked_reason: str | None = None
    blocked_by_task_id: str | None = None
    blocked_by_task_title: str | None = None


class KanbanColumnDTO(BaseModel):
    id: str
    name: str
    wip_limit: int | None = None
    cards: list[KanbanCardDTO] = Field(default_factory=list)


class KanbanSprintDTO(BaseModel):
    id: str
    name: str
    goal: str | None = None
    start_date: date
    end_date: date


class KanbanBoardResponse(BaseModel):
    active_sprint: KanbanSprintDTO | None = None
    columns: list[KanbanColumnDTO] = Field(default_factory=list)
    message: str | None = None


class UpdateWipLimitCommand(BaseModel):
    wip_limit: int | None = Field(default=None, ge=1)


class UpdateWipLimitResponse(BaseModel):
    message: str
    column_id: str
    wip_limit: int | None


class UpdateTaskBlockCommand(BaseModel):
    is_blocked: bool = False
    blocked_reason: str | None = Field(default=None, max_length=500)
    blocked_by_task_id: str | None = Field(default=None, max_length=36)


class UpdateTaskBlockResponse(BaseModel):
    message: str
    task_id: str
    is_blocked: bool
    blocked_reason: str | None
    blocked_by_task_id: str | None
