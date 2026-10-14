"""
DTOs and Commands for Projects application layer.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.domain.entities import ProjectPriority, ProjectStatus


class CreateProjectCommand(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=2000)
    priority: ProjectPriority = ProjectPriority.MEDIA
    tech_stack: list[str] = Field(default_factory=list)
    meeting_link: str | None = Field(default=None, max_length=500)
    manager_id: str = Field(min_length=1, max_length=36)


class UpdateProjectCommand(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=2000)
    priority: ProjectPriority
    tech_stack: list[str] = Field(default_factory=list)
    meeting_link: str | None = Field(default=None, max_length=500)


class UpdateProjectStatusCommand(BaseModel):
    status: ProjectStatus


class AssignProjectManagerCommand(BaseModel):
    manager_id: str = Field(min_length=1, max_length=36)


class AddMemberCommand(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)


class ProjectMemberDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    email: str
    role: str
    joined_at: datetime


class ProjectHealthDTO(BaseModel):
    progress_percent: float
    velocity: float
    open_issues: int


class ProjectDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    owner_id: str
    manager_id: str
    manager_name: str = ""
    priority: ProjectPriority
    tech_stack: list[str]
    meeting_link: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    message: str
