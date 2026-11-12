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


class ProjectPriority(StrEnum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class ProjectStatus(StrEnum):
    PLANIFICACION = "planificacion"
    ACTIVO = "activo"
    EN_PAUSA = "en_pausa"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


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
    manager_id: str
    priority: ProjectPriority
    tech_stack: list[str]
    meeting_link: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def is_deleted(self) -> bool:
        return self.deleted_at is not None
