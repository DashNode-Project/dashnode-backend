"""Kanban application use cases (EP-08)."""

from decimal import Decimal
from typing import Protocol

from app.modules.backlog.application.access import (
    can_manage_backlog_structure,
    can_view_backlog,
)
from app.modules.backlog.domain.entities import StoryTask, StoryTaskStatus, UserStory
from app.modules.kanban.application.dtos import (
    KanbanBoardResponse,
    KanbanCardDTO,
    KanbanColumnDTO,
    KanbanSprintDTO,
    UpdateTaskBlockCommand,
    UpdateTaskBlockResponse,
    UpdateWipLimitCommand,
    UpdateWipLimitResponse,
)
from app.modules.kanban.domain import messages
from app.modules.kanban.domain.entities import STANDARD_COLUMNS, KanbanColumnId
from app.modules.kanban.domain.ports import KanbanRepository
from app.modules.sprints.domain.entities import Sprint
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


class ProjectLookupPort(Protocol):
    def get_project(self, project_id: str) -> object | None: ...
    def is_member(self, project_id: str, user_id: str) -> bool: ...


class SprintLookupPort(Protocol):
    def get_active_for_project(self, project_id: str) -> Sprint | None: ...


class BacklogLookupPort(Protocol):
    def list_stories_by_project(self, project_id: str) -> list[UserStory]: ...
    def list_tasks_by_project(self, project_id: str) -> list[StoryTask]: ...
    def get_story_task(self, task_id: str) -> StoryTask | None: ...
    def update_story_task(self, task: StoryTask) -> None: ...


class UserLookupPort(Protocol):
    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None: ...


class GetKanbanBoardUseCase:
    def __init__(
        self,
        sprints: SprintLookupPort,
        backlog: BacklogLookupPort,
        kanban: KanbanRepository,
        projects: ProjectLookupPort,
        users: UserLookupPort,
    ) -> None:
        self._sprints = sprints
        self._backlog = backlog
        self._kanban = kanban
        self._projects = projects
        self._users = users

    def execute(self, project_id: str, actor: CurrentUser) -> KanbanBoardResponse:
        project = self._projects.get_project(project_id)
        if project is None or (hasattr(project, "is_deleted") and project.is_deleted()):
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_view_backlog(actor, project, self._projects):  # type: ignore[arg-type]
            raise AccessDeniedError()

        wip_limits = self._kanban.get_wip_limits(project_id)
        active_sprint = self._sprints.get_active_for_project(project_id)

        if active_sprint is None:
            empty_cols = [
                KanbanColumnDTO(
                    id=col_id.value,
                    name=col_name,
                    wip_limit=wip_limits.get(col_id.value),
                    cards=[],
                )
                for col_id, col_name in STANDARD_COLUMNS
            ]
            return KanbanBoardResponse(
                active_sprint=None,
                columns=empty_cols,
                message=messages.NO_ACTIVE_SPRINT,
            )

        stories = self._backlog.list_stories_by_project(project_id)
        sprint_stories = [s for s in stories if s.sprint_id == active_sprint.id]
        story_map = {s.id: s for s in sprint_stories}

        all_tasks = self._backlog.list_tasks_by_project(project_id)
        sprint_tasks = [t for t in all_tasks if t.user_story_id in story_map]
        all_tasks_map = {t.id: t for t in all_tasks}

        if actor.role == "developer":
            visible_tasks = [t for t in sprint_tasks if t.assignee_id == actor.id]
        else:
            visible_tasks = sprint_tasks

        cards: list[KanbanCardDTO] = []
        for task in visible_tasks:
            story = story_map.get(task.user_story_id)
            user_info = self._users.get_user_display(task.assignee_id) if task.assignee_id else None
            assignee_name = user_info[0] if user_info else None
            assignee_avatar = user_info[1] if user_info else None

            predecessor = (
                all_tasks_map.get(task.blocked_by_task_id) if task.blocked_by_task_id else None
            )
            has_pending_predecessor = (
                predecessor is not None and predecessor.status != StoryTaskStatus.DONE
            )
            effective_blocked = task.is_blocked or has_pending_predecessor

            reason = task.blocked_reason
            if not reason and has_pending_predecessor and predecessor:
                reason = f"Depende de: {predecessor.name}"

            type_val = (
                task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
            )
            status_val = task.status.value if hasattr(task.status, "value") else str(task.status)

            cards.append(
                KanbanCardDTO(
                    id=task.id,
                    title=task.name,
                    task_type=type_val,
                    status=status_val,
                    assignee_id=task.assignee_id,
                    assignee_name=assignee_name,
                    assignee_avatar_url=assignee_avatar,
                    user_story_id=task.user_story_id,
                    user_story_label=story.label if story else "",
                    user_story_title=story.title if story else "",
                    estimated_hours=float(task.estimated_hours or Decimal("0")),
                    logged_hours=float(task.logged_hours or Decimal("0")),
                    is_blocked=effective_blocked,
                    blocked_reason=reason,
                    blocked_by_task_id=task.blocked_by_task_id,
                    blocked_by_task_title=predecessor.name if predecessor else None,
                )
            )

        columns = [
            KanbanColumnDTO(
                id=col_id.value,
                name=col_name,
                wip_limit=wip_limits.get(col_id.value),
                cards=[c for c in cards if c.status == col_id.value],
            )
            for col_id, col_name in STANDARD_COLUMNS
        ]

        return KanbanBoardResponse(
            active_sprint=KanbanSprintDTO(
                id=active_sprint.id,
                name=active_sprint.name,
                goal=active_sprint.goal,
                start_date=active_sprint.start_date,
                end_date=active_sprint.end_date,
            ),
            columns=columns,
        )


class UpdateColumnWipLimitUseCase:
    def __init__(
        self,
        kanban: KanbanRepository,
        projects: ProjectLookupPort,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._kanban = kanban
        self._projects = projects
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        project_id: str,
        column_id: str,
        cmd: UpdateWipLimitCommand,
        actor: CurrentUser,
    ) -> UpdateWipLimitResponse:
        project = self._projects.get_project(project_id)
        if project is None or (hasattr(project, "is_deleted") and project.is_deleted()):
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_manage_backlog_structure(actor, project):  # type: ignore[arg-type]
            raise AccessDeniedError()

        valid_column_ids = {c.value for c in KanbanColumnId}
        if column_id not in valid_column_ids:
            raise AppError("COLUMN_INVALID", "Columna no válida.", ErrorKind.VALIDATION)

        if cmd.wip_limit is not None and cmd.wip_limit < 1:
            raise AppError("WIP_LIMIT_INVALID", messages.WIP_LIMIT_INVALID, ErrorKind.VALIDATION)

        with self._uow:
            new_id = self._id_gen.generate()
            self._kanban.set_wip_limit(
                new_id=new_id,
                project_id=project_id,
                column_id=column_id,
                wip_limit=cmd.wip_limit,
                when=self._clock.now(),
            )
            self._uow.commit()

        return UpdateWipLimitResponse(
            message=messages.WIP_LIMIT_UPDATED,
            column_id=column_id,
            wip_limit=cmd.wip_limit,
        )


class UpdateTaskBlockUseCase:
    def __init__(
        self,
        backlog: BacklogLookupPort,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        project_id: str,
        task_id: str,
        cmd: UpdateTaskBlockCommand,
        actor: CurrentUser,
    ) -> UpdateTaskBlockResponse:
        project = self._projects.get_project(project_id)
        if project is None or (hasattr(project, "is_deleted") and project.is_deleted()):
            raise AppError("PROJECT_NOT_FOUND", messages.PROJECT_NOT_FOUND, ErrorKind.NOT_FOUND)

        if not can_view_backlog(actor, project, self._projects):  # type: ignore[arg-type]
            raise AccessDeniedError()

        task = self._backlog.get_story_task(task_id)
        if task is None or task.project_id != project_id:
            raise AppError("TASK_NOT_FOUND", messages.TASK_NOT_FOUND, ErrorKind.NOT_FOUND)

        if actor.role == "developer" and task.assignee_id != actor.id:
            raise AccessDeniedError()

        if cmd.blocked_by_task_id:
            if cmd.blocked_by_task_id == task_id:
                raise AppError(
                    "SELF_DEPENDENCY",
                    "Una tarea no puede depender de sí misma.",
                    ErrorKind.VALIDATION,
                )
            predecessor = self._backlog.get_story_task(cmd.blocked_by_task_id)
            if predecessor is None or predecessor.project_id != project_id:
                raise AppError(
                    "PREDECESSOR_NOT_FOUND",
                    "La tarea predecesora no existe en este proyecto.",
                    ErrorKind.NOT_FOUND,
                )

        task.is_blocked = cmd.is_blocked
        task.blocked_reason = cmd.blocked_reason
        task.blocked_by_task_id = cmd.blocked_by_task_id
        task.updated_at = self._clock.now()

        with self._uow:
            self._backlog.update_story_task(task)
            self._uow.commit()

        return UpdateTaskBlockResponse(
            message=messages.TASK_BLOCK_UPDATED,
            task_id=task_id,
            is_blocked=task.is_blocked,
            blocked_reason=task.blocked_reason,
            blocked_by_task_id=task.blocked_by_task_id,
        )
