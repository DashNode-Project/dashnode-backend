"""
Use cases for Project management (EP-03).
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from app.modules.projects.application.access import (
    can_create_project,
    can_manage_project,
    can_view_project,
)
from app.modules.projects.application.dtos import (
    AddMemberCommand,
    AssignProjectManagerCommand,
    CreateProjectCommand,
    MessageResponse,
    ProjectDTO,
    ProjectMemberDTO,
    UpdateProjectCommand,
    UpdateProjectStatusCommand,
)
from app.modules.projects.application.mappers import project_to_dto
from app.modules.projects.domain import messages
from app.modules.projects.domain.entities import (
    Project,
    ProjectMember,
    ProjectPriority,
    ProjectRole,
    ProjectStatus,
)
from app.modules.projects.domain.ports import ManagerLookup, ProjectRepository
from app.modules.projects.domain.rules import (
    parse_status,
    validate_manager_id,
    validate_meeting_link,
    validate_project_name,
)
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


def _validation_error(fields: dict[str, str]) -> AppError:
    return AppError(
        "PROJECT_VALIDATION",
        "La solicitud no es válida.",
        ErrorKind.VALIDATION,
        fields,
    )


def _require_active_manager(lookup: ManagerLookup, manager_id: str) -> None:
    if not lookup.is_active_manager(manager_id):
        raise _validation_error({"manager_id": messages.MANAGER_MUST_BE_MANAGER_ROLE})


class CreateProjectUseCase:
    """HU_DN_02_22: create project (admin/manager only)."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        manager_lookup: ManagerLookup,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._managers = manager_lookup
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: CreateProjectCommand, actor: CurrentUser) -> ProjectDTO:
        if not can_create_project(actor):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_project_name(cmd.name))
        fields.update(validate_manager_id(cmd.manager_id))
        fields.update(validate_meeting_link(cmd.meeting_link))
        if fields:
            raise _validation_error(fields)

        _require_active_manager(self._managers, cmd.manager_id)

        now = self._clock.now()
        project_id = self._id_gen.generate()
        stack = [tag.strip() for tag in cmd.tech_stack if tag.strip()]

        project = Project(
            id=project_id,
            name=cmd.name.strip(),
            description=(cmd.description or "").strip(),
            owner_id=actor.id,
            manager_id=cmd.manager_id,
            priority=ProjectPriority(cmd.priority.value),
            tech_stack=stack,
            meeting_link=cmd.meeting_link.strip() if cmd.meeting_link else None,
            status=ProjectStatus.PLANIFICACION,
            created_at=now,
            updated_at=now,
        )

        manager_member = ProjectMember(
            project_id=project_id,
            user_id=cmd.manager_id,
            role=ProjectRole.LEAD,
            joined_at=now,
        )
        members = [manager_member]
        if actor.id != cmd.manager_id:
            members.append(
                ProjectMember(
                    project_id=project_id,
                    user_id=actor.id,
                    role=ProjectRole.MEMBER,
                    joined_at=now,
                )
            )

        with self._uow:
            self._repo.save(project)
            for member in members:
                self._repo.add_member(member)
            self._uow.commit()

        return project_to_dto(project)


class UpdateProjectUseCase:
    """HU_DN_02_23: edit project metadata."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._clock = clock
        self._uow = uow

    def execute(self, project_id: str, cmd: UpdateProjectCommand, actor: CurrentUser) -> ProjectDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_project(actor, project):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_project_name(cmd.name))
        fields.update(validate_meeting_link(cmd.meeting_link))
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        project.name = cmd.name.strip()
        project.description = (cmd.description or "").strip()
        project.priority = cmd.priority
        project.tech_stack = [tag.strip() for tag in cmd.tech_stack if tag.strip()]
        project.meeting_link = cmd.meeting_link.strip() if cmd.meeting_link else None
        project.updated_at = now

        with self._uow:
            self._repo.update(project)
            self._uow.commit()

        return project_to_dto(project)


class UpdateProjectStatusUseCase:
    """HU_DN_02_24: change lifecycle status."""

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
        self, project_id: str, cmd: UpdateProjectStatusCommand, actor: CurrentUser
    ) -> MessageResponse:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_project(actor, project):
            raise AccessDeniedError()

        status = parse_status(cmd.status.value)
        if status is None:
            raise AppError(
                "PROJECT_STATUS_INVALID",
                messages.PROJECT_STATUS_INVALID,
                ErrorKind.VALIDATION,
                {"status": messages.PROJECT_STATUS_INVALID},
            )

        now = self._clock.now()
        project.status = status
        project.updated_at = now

        with self._uow:
            self._repo.update(project)
            self._uow.commit()

        return MessageResponse(message=messages.PROJECT_STATUS_UPDATED)


class AssignProjectManagerUseCase:
    """HU_DN_02_25: reassign responsible manager."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        manager_lookup: ManagerLookup,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._managers = manager_lookup
        self._clock = clock
        self._uow = uow

    def execute(
        self, project_id: str, cmd: AssignProjectManagerCommand, actor: CurrentUser
    ) -> MessageResponse:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_project(actor, project):
            raise AccessDeniedError()

        fields = validate_manager_id(cmd.manager_id)
        if fields:
            raise _validation_error(fields)

        _require_active_manager(self._managers, cmd.manager_id)

        now = self._clock.now()
        project.manager_id = cmd.manager_id
        project.updated_at = now

        with self._uow:
            self._repo.update(project)
            self._repo.add_member(
                ProjectMember(
                    project_id=project_id,
                    user_id=cmd.manager_id,
                    role=ProjectRole.LEAD,
                    joined_at=now,
                )
            )
            self._uow.commit()

        return MessageResponse(message=messages.MANAGER_UPDATED)


class DeleteProjectUseCase:
    """HU_DN_02_26: admin-only soft delete with cascade and audit."""

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

    def execute(self, project_id: str, actor: CurrentUser) -> MessageResponse:
        if actor.role != "admin":
            raise AccessDeniedError()

        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        now = self._clock.now()
        with self._uow:
            self._repo.soft_delete_cascade(project_id, now)
            self._repo.add_audit_entry(
                entry_id=self._id_gen.generate(),
                user_id=actor.id,
                action="project.deleted",
                resource_type="project",
                resource_id=project_id,
                when=now,
            )
            self._uow.commit()

        return MessageResponse(message=messages.PROJECT_DELETED)


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

    def execute(self, project_id: str, cmd: AddMemberCommand, actor_id: str) -> ProjectMemberDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise ValueError("Proyecto no encontrado.")

        if project.owner_id != actor_id and not self._repo.is_member(project_id, actor_id):
            raise AccessDeniedError()

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
    """Lists projects visible to the authenticated user."""

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._repo = project_repo

    def execute(self, user: CurrentUser) -> list[ProjectDTO]:
        projects = self._repo.list_visible_for_user(user.id, role=user.role)
        return [project_to_dto(p) for p in projects]


class GetProjectUseCase:
    """Retrieves project details for authorized users."""

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._repo = project_repo

    def execute(self, project_id: str, user: CurrentUser) -> ProjectDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_view_project(user, project, self._repo):
            raise AccessDeniedError()

        return project_to_dto(project)
