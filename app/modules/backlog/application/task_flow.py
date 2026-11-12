"""Time logs, task status and personal task list (HU_DN_04_56, 57, 61)."""

from decimal import Decimal

from app.modules.backlog.application.access import can_manage_story_tasks, can_view_backlog
from app.modules.backlog.application.dtos import (
    ChangeTaskStatusCommand,
    ChangeTaskStatusResponse,
    LogTaskHoursCommand,
    LogTaskHoursResponse,
    MyTaskItemDTO,
    MyTasksResponse,
)
from app.modules.backlog.application.ports import ProjectLookupPort
from app.modules.backlog.application.use_cases import _require_project
from app.modules.backlog.domain import messages
from app.modules.backlog.domain.entities import (
    MANUAL_TASK_STATUSES,
    StoryTaskStatus,
    parse_story_task_status,
)
from app.modules.backlog.domain.ports import BacklogRepository
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


def _hours_error(hours: Decimal) -> str | None:
    if not hours.is_finite():
        return messages.HOURS_MUST_BE_POSITIVE
    exponent = hours.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        return messages.HOURS_DECIMALS
    if hours <= 0:
        return messages.HOURS_MUST_BE_POSITIVE
    if hours > Decimal("24"):
        return messages.HOURS_MAX_PER_ENTRY
    return None


class LogStoryTaskHoursUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(
        self, project_id: str, task_id: str, cmd: LogTaskHoursCommand, actor: CurrentUser
    ) -> LogTaskHoursResponse:
        task = self._backlog.get_story_task(task_id)
        if task is None or task.project_id != project_id:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        project = _require_project(self._projects, project_id)
        if not can_manage_story_tasks(actor, project, self._projects):
            raise AppError("NOT_PROJECT_MEMBER", messages.NOT_PROJECT_MEMBER, ErrorKind.FORBIDDEN)
        problem = _hours_error(cmd.hours_spent)
        comment = (cmd.comment or "").strip()
        if comment and len(comment) > 500:
            problem = messages.HOURS_COMMENT_TOO_LONG
        if problem:
            raise AppError("HOURS_INVALID", problem, ErrorKind.VALIDATION, {"hours_spent": problem})
        now = self._clock.now()
        task.logged_hours = (task.logged_hours or Decimal("0")) + cmd.hours_spent
        task.updated_at = now
        with self._uow:
            self._backlog.add_time_log(
                log_id=self._id_gen.generate(),
                task_id=task.id,
                user_id=actor.id,
                hours=cmd.hours_spent,
                comment=comment or None,
                when=now,
            )
            self._backlog.update_story_task(task)
            self._uow.commit()
        return LogTaskHoursResponse(
            message=messages.HOURS_LOGGED, total_logged_hours=task.logged_hours
        )


class ChangeStoryTaskStatusUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(
        self, project_id: str, task_id: str, cmd: ChangeTaskStatusCommand, actor: CurrentUser
    ) -> ChangeTaskStatusResponse:
        task = self._backlog.get_story_task(task_id)
        if task is None or task.project_id != project_id:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        project = _require_project(self._projects, project_id)
        if not can_view_backlog(actor, project, self._projects):
            raise AccessDeniedError()
        target = parse_story_task_status(cmd.status.strip())
        if target is None:
            raise AppError("STATUS_INVALID", messages.TASK_STATUS_INVALID, ErrorKind.VALIDATION)
        if task.status == StoryTaskStatus.CORRECTION or target == StoryTaskStatus.CORRECTION:
            raise AppError(
                "STATUS_CORRECTION", messages.TASK_STATUS_CORRECTION, ErrorKind.VALIDATION
            )
        if target not in MANUAL_TASK_STATUSES:
            raise AppError(
                "STATUS_CORRECTION", messages.TASK_STATUS_CORRECTION, ErrorKind.VALIDATION
            )
        if actor.role == "developer" and task.assignee_id != actor.id:
            raise AppError("STATUS_OWN_ONLY", messages.TASK_STATUS_OWN_ONLY, ErrorKind.FORBIDDEN)
        if actor.role == "manager" and project.manager_id != actor.id:
            raise AccessDeniedError()
        now = self._clock.now()
        previous = task.status.value
        task.status = target
        task.updated_at = now
        with self._uow:
            self._backlog.add_status_history(
                history_id=self._id_gen.generate(),
                task_id=task.id,
                user_id=actor.id,
                previous_status=previous,
                new_status=target.value,
                when=now,
            )
            self._backlog.update_story_task(task)
            self._uow.commit()
        return ChangeTaskStatusResponse(message=messages.TASK_STATUS_UPDATED, status=target.value)


class ListMyTasksUseCase:
    def __init__(self, backlog: BacklogRepository, projects: ProjectLookupPort) -> None:
        self._backlog = backlog
        self._projects = projects

    def execute(
        self, actor: CurrentUser, *, project_id: str | None, status: str | None
    ) -> MyTasksResponse:
        rows = self._backlog.list_tasks_for_assignee(actor.id)
        if not rows:
            return MyTasksResponse(tasks=[], message=messages.MY_TASKS_EMPTY)
        wanted_status = parse_story_task_status(status) if status else None
        items: list[MyTaskItemDTO] = []
        for task in rows:
            if project_id and task.project_id != project_id:
                continue
            if wanted_status and task.status != wanted_status:
                continue
            project = self._projects.get_project(task.project_id)
            story = self._backlog.get_user_story(task.user_story_id)
            if project is None or story is None:
                continue
            items.append(
                MyTaskItemDTO(
                    id=task.id,
                    name=task.name,
                    project={"id": project.id, "name": project.name},
                    user_story={"id": story.id, "title": story.title},
                    status=task.status.value,
                    estimated_hours=task.estimated_hours,
                    logged_hours=task.logged_hours,
                )
            )
        if not items:
            return MyTasksResponse(tasks=[], message=messages.MY_TASKS_FILTER_EMPTY)
        return MyTasksResponse(tasks=items)
