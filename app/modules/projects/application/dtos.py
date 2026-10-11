"""
DTOs and Commands for Projects application layer.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.domain.entities import ProjectRole


class CreateProjectCommand(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str = Field(default="", max_length=1000)


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
    created_at: datetime
    updated_at: datetime
