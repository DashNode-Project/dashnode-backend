"""
Domain entities and value objects for Projects module.
@sad AD-08, 4.1.2
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ProjectRole(StrEnum):
    LEAD = "lead"
    MEMBER = "member"


@dataclass
class ProjectMember:
    project_id: str
    user_id: str
    role: ProjectRole
    joined_at: datetime


@dataclass
class Project:
    id: str
    name: str
    description: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    def validate_name(self) -> None:
        """Validates that project name meets system length constraints."""
        clean = self.name.strip()
        if len(clean) < 3:
            raise ValueError("El nombre del proyecto debe tener al menos 3 caracteres.")
        if len(clean) > 100:
            raise ValueError("El nombre del proyecto no puede exceder 100 caracteres.")
