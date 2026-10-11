"""
Use cases for Project management.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from app.modules.projects.application.dtos import (
    AddMemberCommand,
    CreateProjectCommand,
    ProjectDTO,
    ProjectMemberDTO,
)
from app.modules.projects.domain.entities import Project, ProjectMember, ProjectRole
from app.modules.projects.domain.ports import ProjectRepository
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork


class CreateProjectUseCase:
    """Handles project creation and sets creator as Lead member."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: CreateProjectCommand, owner_id: str) -> ProjectDTO:
        now = self._clock.now()
        project_id = self._id_gen.generate()

        project = Project(
            id=project_id,
            name=cmd.name.strip(),
            description=cmd.description.strip(),
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
        )
        project.validate_name()

        owner_member = ProjectMember(
            project_id=project_id,
            user_id=owner_id,
            role=ProjectRole.LEAD,
            joined_at=now,
        )

        with self._uow:
            self._repo.save(project)
            self._repo.add_member(owner_member)
            self._uow.commit()

        return ProjectDTO(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=project.owner_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class AddProjectMemberUseCase:
    """Adds a new member to an existing project."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._clock = clock
        self._uow = uow

    def execute(
        self, project_id: str, cmd: AddMemberCommand, actor_id: str
    ) -> ProjectMemberDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise ValueError("Proyecto no encontrado.")

        # SAD RN-PRY-01: Only project owner or lead can manage membership
        if project.owner_id != actor_id and not self._repo.is_member(project_id, actor_id):
            raise ValueError("No tienes permisos para agregar miembros a este proyecto.")

        if self._repo.is_member(project_id, cmd.user_id):
            raise ValueError("El usuario ya es miembro de este proyecto.")

        now = self._clock.now()
        member = ProjectMember(
            project_id=project_id,
            user_id=cmd.user_id,
            role=cmd.role,
            joined_at=now,
        )

        with self._uow:
            self._repo.add_member(member)
            self._uow.commit()

        return ProjectMemberDTO(
            project_id=member.project_id,
            user_id=member.user_id,
            role=member.role,
            joined_at=member.joined_at,
        )


class ListProjectsUseCase:
    """Lists all projects associated with a given user."""

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._repo = project_repo

    def execute(self, user_id: str) -> list[ProjectDTO]:
        projects = self._repo.list_by_user(user_id)
        return [
            ProjectDTO(
                id=p.id,
                name=p.name,
                description=p.description,
                owner_id=p.owner_id,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
        ]


class GetProjectUseCase:
    """Retrieves project details by id for authorized members."""

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._repo = project_repo

    def execute(self, project_id: str, user_id: str) -> ProjectDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise ValueError("Proyecto no encontrado.")

        if project.owner_id != user_id and not self._repo.is_member(project_id, user_id):
            raise ValueError("No tienes acceso a este proyecto.")

        return ProjectDTO(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=project.owner_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
