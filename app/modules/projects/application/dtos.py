"""
DTOs and Commands for Projects application layer.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.domain.entities import ProjectPriority, ProjectRole, ProjectStatus


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
    user_id: str
    role: ProjectRole = ProjectRole.MEMBER


class ProjectMemberDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    user_id: str
    role: ProjectRole
    joined_at: datetime


class ProjectDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    owner_id: str
    manager_id: str
    priority: ProjectPriority
    tech_stack: list[str]
    meeting_link: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    message: str
