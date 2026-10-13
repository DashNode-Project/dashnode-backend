"""Maps domain Project entities to DTOs."""

from app.modules.projects.application.dtos import ProjectDTO
from app.modules.projects.domain.entities import Project


def project_to_dto(project: Project, *, manager_name: str = "") -> ProjectDTO:
    return ProjectDTO(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        manager_id=project.manager_id,
        manager_name=manager_name,
        priority=project.priority,
        tech_stack=list(project.tech_stack),
        meeting_link=project.meeting_link,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
