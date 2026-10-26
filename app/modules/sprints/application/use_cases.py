"""Sprint use cases (EP-07)."""

from datetime import date

from sqlalchemy.exc import IntegrityError

from app.modules.backlog.application.access import ProjectContext
from app.modules.backlog.application.ports import ProjectLookupPort
from app.modules.backlog.domain.ports import BacklogRepository
from app.modules.sprints.application.access import can_manage_sprints, can_view_sprints
from app.modules.sprints.application.dtos import (
    AssignStoryToSprintCommand,
    AssignStoryToSprintResponse,
    CreateSprintCommand,
    CreateSprintResponse,
    CurrentSprintMetricsDTO,
    CurrentSprintResponse,
    SprintListResponse,
    SprintSummaryDTO,
    StartSprintResponse,
)
from app.modules.sprints.application.metrics import (
    compute_sprint_points,
    days_remaining,
    progress_percentage,
)
from app.modules.sprints.domain import messages
from app.modules.sprints.domain.entities import Sprint, SprintStatus
from app.modules.sprints.domain.ports import SprintRepository
from app.modules.sprints.domain.rules import validate_create_sprint
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.errors import AppError, ErrorKind


def _require_project(project_id: str, lookup: ProjectLookupPort) -> ProjectContext:
    project = lookup.get_project(project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Proyecto no encontrado.", ErrorKind.NOT_FOUND)
    return project


def _deny_sprint_manage() -> AppError:
    return AppError("ACCESS_DENIED", messages.SPRINT_ACCESS_DENIED, ErrorKind.FORBIDDEN)


class CreateSprintUseCase:
    def __init__(
        self,
        sprints: SprintRepository,
        projects: ProjectLookupPort,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._sprints = sprints
        self._projects = projects
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(
        self, project_id: str, cmd: CreateSprintCommand, actor: CurrentUser
    ) -> CreateSprintResponse:
        project = _require_project(project_id, self._projects)
        if not can_manage_sprints(actor, project):
            raise _deny_sprint_manage()

        goal = cmd.goal.strip() if cmd.goal else None
        if goal == "":
            goal = None
        fields = validate_create_sprint(
            name=cmd.name,
            goal=goal,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
        )
        if fields:
            raise AppError(
                "SPRINT_VALIDATION",
                fields.get("end_date", fields.get("name", messages.SPRINT_NAME_REQUIRED)),
                ErrorKind.VALIDATION,
                fields,
            )

        now = self._clock.now()
        sprint_id = self._id_gen.generate()
        sprint = Sprint(
            id=sprint_id,
            project_id=project_id,
            name=cmd.name.strip(),
            goal=goal,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            status=SprintStatus.PLANNING,
            created_at=now,
        )
        self._sprints.save(sprint)
        self._uow.commit()
        return CreateSprintResponse(
            id=sprint_id,
            message=messages.SPRINT_CREATED,
            status=SprintStatus.PLANNING,
        )


class ListProjectSprintsUseCase:
    def __init__(
        self,
        sprints: SprintRepository,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
    ) -> None:
        self._sprints = sprints
        self._backlog = backlog
        self._projects = projects

    def execute(self, project_id: str, actor: CurrentUser) -> SprintListResponse:
        project = _require_project(project_id, self._projects)
        if not can_view_sprints(actor, project, self._projects):
            raise _deny_sprint_manage()

        stories = self._backlog.list_stories_by_project(project_id)
        tasks = self._backlog.list_tasks_by_project(project_id)
        items: list[SprintSummaryDTO] = []
        for sprint in self._sprints.list_by_project(project_id):
            total, _, _ = compute_sprint_points(stories, tasks, sprint.id)
            count = sum(1 for s in stories if s.sprint_id == sprint.id)
            items.append(
                SprintSummaryDTO(
                    id=sprint.id,
                    name=sprint.name,
                    goal=sprint.goal,
                    start_date=sprint.start_date,
                    end_date=sprint.end_date,
                    status=sprint.status,
                    story_count=count,
                    total_points=total,
                )
            )
        return SprintListResponse(items=items)


class AssignUserStoryToSprintUseCase:
    def __init__(
        self,
        sprints: SprintRepository,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._sprints = sprints
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        project_id: str,
        story_id: str,
        cmd: AssignStoryToSprintCommand,
        actor: CurrentUser,
    ) -> AssignStoryToSprintResponse:
        project = _require_project(project_id, self._projects)
        if not can_manage_sprints(actor, project):
            raise _deny_sprint_manage()

        sprint = self._sprints.get_by_id(cmd.sprint_id)
        if sprint is None or sprint.project_id != project_id:
            raise AppError("SPRINT_NOT_FOUND", messages.SPRINT_NOT_FOUND, ErrorKind.NOT_FOUND)
        if sprint.status not in (SprintStatus.PLANNING, SprintStatus.ACTIVE):
            raise AppError("SPRINT_NOT_FOUND", messages.SPRINT_NOT_FOUND, ErrorKind.NOT_FOUND)

        story = self._backlog.get_user_story(story_id)
        if story is None or story.project_id != project_id:
            raise AppError(
                "STORY_NOT_FOUND", "Historia de usuario no encontrada.", ErrorKind.NOT_FOUND
            )

        story.sprint_id = cmd.sprint_id
        story.updated_at = self._clock.now()
        self._backlog.update_user_story(story)
        self._uow.commit()

        stories = self._backlog.list_stories_by_project(project_id)
        tasks = self._backlog.list_tasks_by_project(project_id)
        total, _, _ = compute_sprint_points(stories, tasks, cmd.sprint_id)
        return AssignStoryToSprintResponse(
            message=messages.STORY_ASSIGNED,
            sprint_total_points=total,
        )


class StartSprintUseCase:
    def __init__(
        self,
        sprints: SprintRepository,
        projects: ProjectLookupPort,
        uow: UnitOfWork,
    ) -> None:
        self._sprints = sprints
        self._projects = projects
        self._uow = uow

    def execute(self, project_id: str, sprint_id: str, actor: CurrentUser) -> StartSprintResponse:
        project = _require_project(project_id, self._projects)
        if not can_manage_sprints(actor, project):
            raise _deny_sprint_manage()

        sprint = self._sprints.get_by_id(sprint_id)
        if sprint is None or sprint.project_id != project_id:
            raise AppError("SPRINT_NOT_FOUND", messages.SPRINT_NOT_FOUND, ErrorKind.NOT_FOUND)
        if sprint.status != SprintStatus.PLANNING:
            raise AppError("SPRINT_NOT_FOUND", messages.SPRINT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if self._sprints.count_stories(sprint_id) < 1:
            raise AppError(
                "SPRINT_NO_STORIES",
                messages.SPRINT_START_NO_STORIES,
                ErrorKind.VALIDATION,
            )

        if self._sprints.has_other_active_sprint(project_id, sprint_id):
            raise AppError(
                "SPRINT_ALREADY_ACTIVE",
                messages.SPRINT_ALREADY_ACTIVE,
                ErrorKind.CONFLICT,
            )

        try:
            sprint.status = SprintStatus.ACTIVE
            self._sprints.update(sprint)
            self._uow.commit()
        except IntegrityError as exc:
            self._uow.rollback()
            raise AppError(
                "SPRINT_ALREADY_ACTIVE",
                messages.SPRINT_ALREADY_ACTIVE,
                ErrorKind.CONFLICT,
            ) from exc

        return StartSprintResponse(message=messages.SPRINT_STARTED, status=SprintStatus.ACTIVE)


class GetCurrentSprintUseCase:
    def __init__(
        self,
        sprints: SprintRepository,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
    ) -> None:
        self._sprints = sprints
        self._backlog = backlog
        self._projects = projects
        self._clock = clock

    def execute(self, project_id: str, actor: CurrentUser) -> CurrentSprintResponse:
        project = _require_project(project_id, self._projects)
        if not can_view_sprints(actor, project, self._projects):
            raise _deny_sprint_manage()

        sprint = self._sprints.get_active_for_project(project_id)
        if sprint is None:
            return CurrentSprintResponse(sprint=None, message=messages.NO_ACTIVE_SPRINT)

        stories = self._backlog.list_stories_by_project(project_id)
        tasks = self._backlog.list_tasks_by_project(project_id)
        total, completed, pending = compute_sprint_points(stories, tasks, sprint.id)
        today: date = self._clock.now().date()
        return CurrentSprintResponse(
            sprint=CurrentSprintMetricsDTO(
                id=sprint.id,
                name=sprint.name,
                goal=sprint.goal,
                days_remaining=days_remaining(sprint.end_date, today),
                total_points=total,
                completed_points=completed,
                pending_points=pending,
                progress_percentage=progress_percentage(total, completed),
            ),
        )
