"""
DTOs and Commands for Tasks application layer.
@sad AD-09, 4.1.3
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.domain.entities import TaskPriority, TaskStatus


class CreateTaskCommand(BaseModel):
    project_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: str | None = None


class UpdateTaskStatusCommand(BaseModel):
    status: TaskStatus


class AssignTaskCommand(BaseModel):
    assignee_id: str | None = None


class TaskDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    assignee_id: str | None
    creator_id: str
    has_open_fix: bool
    created_at: datetime
    updated_at: datetime
