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
    ProjectHealthDTO,
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
from app.modules.projects.domain.health import compute_health_indicators
from app.modules.projects.domain.ports import (
    ActiveUserLookup,
    ManagerLookup,
    ProjectDeletionCollaborator,
    ProjectRepository,
)
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
    """HU_DN_02_22: create project (manager only)."""

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
    """HU_DN_02_26: managing manager soft delete with cascade and audit."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        deletion_collaborator: ProjectDeletionCollaborator | None = None,
    ) -> None:
        self._repo = project_repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._deletion_collaborator = deletion_collaborator

    def execute(self, project_id: str, actor: CurrentUser) -> MessageResponse:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_project(actor, project):
            raise AccessDeniedError()

        now = self._clock.now()
        with self._uow:
            self._repo.soft_delete_cascade(project_id, now)
            if self._deletion_collaborator is not None:
                self._deletion_collaborator.after_project_soft_deleted(project_id, now)
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
    """HU_DN_02_27: add active user as project member (managing manager)."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        users: ActiveUserLookup,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._users = users
        self._clock = clock
        self._uow = uow

    def execute(
        self, project_id: str, cmd: AddMemberCommand, actor: CurrentUser
    ) -> MessageResponse:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_project(actor, project):
            raise AccessDeniedError()

        user_id = cmd.user_id.strip()
        if not user_id:
            raise _validation_error({"user_id": messages.MEMBER_USER_REQUIRED})

        if not self._users.is_active_user(user_id):
            raise _validation_error({"user_id": messages.MEMBER_USER_REQUIRED})

        if self._repo.is_member(project_id, user_id):
            raise _validation_error({"user_id": messages.MEMBER_ALREADY_EXISTS})

        now = self._clock.now()
        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=ProjectRole.MEMBER,
            joined_at=now,
        )

        with self._uow:
            self._repo.add_member(member)
            self._uow.commit()

        return MessageResponse(message=messages.MEMBER_ADDED)


class RemoveProjectMemberUseCase:
    """HU_DN_02_28: remove member; manager responsible cannot be removed."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = project_repo
        self._clock = clock
        self._uow = uow

    def execute(self, project_id: str, member_user_id: str, actor: CurrentUser) -> MessageResponse:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_project(actor, project):
            raise AccessDeniedError()

        if member_user_id == project.manager_id:
            raise _validation_error({"user_id": messages.MEMBER_REMOVE_MANAGER_FORBIDDEN})

        if not self._repo.is_member(project_id, member_user_id):
            raise AppError("PROJECT_MEMBER", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        now = self._clock.now()
        with self._uow:
            self._repo.clear_assignee_tasks(project_id, member_user_id, when=now)
            self._repo.remove_member(project_id, member_user_id)
            self._uow.commit()

        return MessageResponse(message=messages.MEMBER_REMOVED)


class ListProjectMembersUseCase:
    """Lists members with profile data for project summary."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        users: ActiveUserLookup,
    ) -> None:
        self._repo = project_repo
        self._users = users

    def execute(self, project_id: str, actor: CurrentUser) -> list[ProjectMemberDTO]:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_view_project(actor, project, self._repo):
            raise AccessDeniedError()

        rows: list[ProjectMemberDTO] = []
        for member in self._repo.get_members(project_id):
            profile = self._users.get_member_profile(member.user_id)
            if profile is None:
                continue
            rows.append(
                ProjectMemberDTO(
                    user_id=member.user_id,
                    name=profile.name,
                    email=profile.email,
                    role=profile.role,
                    joined_at=member.joined_at,
                )
            )
        return rows


class GetProjectHealthUseCase:
    """HU_DN_02_31: progress, velocity and open issues for summary tab."""

    def __init__(self, project_repo: ProjectRepository) -> None:
        self._repo = project_repo

    def execute(self, project_id: str, actor: CurrentUser) -> ProjectHealthDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_view_project(actor, project, self._repo):
            raise AccessDeniedError()

        snapshot = self._repo.get_health_snapshot(project_id)
        indicators = compute_health_indicators(snapshot)
        return ProjectHealthDTO(
            progress_percent=indicators.progress_percent,
            velocity=indicators.velocity,
            open_issues=indicators.open_issues,
        )


class ListProjectsUseCase:
    """HU_DN_02_29: list projects scoped by role and membership."""

    def __init__(self, project_repo: ProjectRepository, users: ActiveUserLookup) -> None:
        self._repo = project_repo
        self._users = users

    def execute(self, user: CurrentUser) -> list[ProjectDTO]:
        if user.role == "admin":
            from app.shared.domain.authorization import AccessDeniedError

            raise AccessDeniedError()
        projects = self._repo.list_visible_for_user(user.id, role=user.role)
        return [
            project_to_dto(
                p,
                manager_name=self._users.display_name(p.manager_id) or "",
            )
            for p in projects
        ]


class GetProjectUseCase:
    """Retrieves project details for authorized users."""

    def __init__(self, project_repo: ProjectRepository, users: ActiveUserLookup) -> None:
        self._repo = project_repo
        self._users = users

    def execute(self, project_id: str, user: CurrentUser) -> ProjectDTO:
        project = self._repo.get_by_id(project_id)
        if project is None:
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_view_project(user, project, self._repo):
            raise AccessDeniedError()

        return project_to_dto(
            project,
            manager_name=self._users.display_name(project.manager_id) or "",
        )
