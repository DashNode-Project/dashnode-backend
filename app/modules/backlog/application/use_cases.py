"""Backlog use cases (EP-06)."""

from dataclasses import dataclass
from decimal import Decimal

from app.modules.backlog.application.access import (
    ProjectContext,
    can_manage_backlog_structure,
    can_manage_story_tasks,
    can_view_backlog,
)
from app.modules.backlog.application.dtos import (
    AssignStoryPointsCommand,
    AssignStoryTaskCommand,
    AssignTaskStoryPointsCommand,
    BacklogTreeDTO,
    CreateEpicCommand,
    CreateStoryTaskCommand,
    CreateUserStoryCommand,
    EpicDTO,
    EpicWithStoriesDTO,
    MessageResponse,
    StoryTaskDTO,
    UpdateEpicCommand,
    UpdateEstimatedHoursCommand,
    UpdateStoryTaskCommand,
    UpdateUserStoryCommand,
    UserStoryDTO,
)
from app.modules.backlog.application.ports import ActiveMemberLookupPort, ProjectLookupPort
from app.modules.backlog.domain import messages
from app.modules.backlog.domain.entities import (
    Epic,
    EstimationMode,
    MoscowPriority,
    StoryTask,
    StoryTaskStatus,
    UserStory,
)
from app.modules.backlog.domain.ports import BacklogRepository
from app.modules.backlog.domain.rules import (
    parse_moscow,
    parse_task_type,
    validate_epic_description,
    validate_epic_name,
    validate_estimated_hours,
    validate_story_points,
    validate_story_reason,
    validate_story_role,
    validate_story_title,
    validate_task_name,
)
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


def _validation_error(fields: dict[str, str]) -> AppError:
    return AppError(
        "BACKLOG_VALIDATION",
        "La solicitud no es válida.",
        ErrorKind.VALIDATION,
        fields,
    )


def _require_project(projects: ProjectLookupPort, project_id: str) -> ProjectContext:
    project = projects.get_project(project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Proyecto no encontrado.", ErrorKind.NOT_FOUND)
    return project


def _epic_dto(epic: Epic) -> EpicDTO:
    return EpicDTO(
        id=epic.id,
        project_id=epic.project_id,
        name=epic.name,
        description=epic.description,
        color=epic.color,
        sort_order=epic.sort_order,
        created_at=epic.created_at,
        updated_at=epic.updated_at,
    )


def _story_dto(story: UserStory) -> UserStoryDTO:
    return UserStoryDTO(
        id=story.id,
        epic_id=story.epic_id,
        project_id=story.project_id,
        title=story.title,
        user_role=story.user_role,
        reason=story.reason,
        acceptance_criteria=story.acceptance_criteria,
        moscow_priority=story.moscow_priority,
        story_points=story.story_points,
        estimation_mode=story.estimation_mode,
        sprint_id=story.sprint_id,
        sort_order=story.sort_order,
        created_at=story.created_at,
        updated_at=story.updated_at,
        label=story.label,
    )


def _task_dto(task: StoryTask) -> StoryTaskDTO:
    return StoryTaskDTO(
        id=task.id,
        user_story_id=task.user_story_id,
        project_id=task.project_id,
        name=task.name,
        task_type=task.task_type,
        notes=task.notes,
        status=task.status.value,
        assignee_id=task.assignee_id,
        estimated_hours=task.estimated_hours,
        story_points=task.story_points,
        logged_hours=task.logged_hours,
        label=task.label,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


_PRIORITY = {
    "CRITICAL": MoscowPriority.MUST_HAVE,
    "HIGH": MoscowPriority.SHOULD_HAVE,
    "MEDIUM": MoscowPriority.COULD_HAVE,
    "LOW": MoscowPriority.WONT_HAVE,
    "must_have": MoscowPriority.MUST_HAVE,
    "should_have": MoscowPriority.SHOULD_HAVE,
    "could_have": MoscowPriority.COULD_HAVE,
    "wont_have": MoscowPriority.WONT_HAVE,
}


@dataclass
class BacklogFilters:
    q: str | None = None
    priority: str | None = None
    assigned_to: str | None = None
    label: str | None = None


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


class GetProjectBacklogUseCase:
    def __init__(self, backlog: BacklogRepository, projects: ProjectLookupPort) -> None:
        self._backlog = backlog
        self._projects = projects

    def execute(
        self,
        project_id: str,
        actor: CurrentUser,
        filters: BacklogFilters | None = None,
    ) -> BacklogTreeDTO:
        project = _require_project(self._projects, project_id)
        if not can_view_backlog(actor, project, self._projects):
            raise AccessDeniedError()

        query = filters or BacklogFilters()
        epics = self._backlog.list_epics_by_project(project_id)
        stories = self._backlog.list_stories_by_project(project_id)
        tasks = self._backlog.list_tasks_by_project(project_id)
        if actor.role == "developer":
            tasks = [task for task in tasks if task.assignee_id == actor.id]

        needle = (query.q or "").strip()
        priority = _PRIORITY.get((query.priority or "").strip())
        label = (query.label or "").strip().casefold()
        assignee = (query.assigned_to or "").strip()

        def task_ok(task: StoryTask, story: UserStory) -> bool:
            if assignee == "unassigned" and task.assignee_id is not None:
                return False
            if assignee and assignee != "unassigned" and task.assignee_id != assignee:
                return False
            if label and task.label.casefold() != label and story.label.casefold() != label:
                return False
            if not needle:
                return True
            return (
                _contains(task.name, needle)
                or _contains(task.notes, needle)
                or _contains(story.title, needle)
            )

        def story_ok(story: UserStory) -> bool:
            if priority is not None and story.moscow_priority != priority:
                return False
            if label and story.label.casefold() != label:
                return False
            if not needle:
                return True
            return _contains(story.title, needle) or _contains(story.reason, needle)

        filtered_tasks: list[StoryTask] = []
        stories_by_id = {story.id: story for story in stories}
        for task in tasks:
            parent = stories_by_id.get(task.user_story_id)
            if parent is None:
                continue
            if priority is not None and parent.moscow_priority != priority:
                continue
            if task_ok(task, parent):
                filtered_tasks.append(task)

        task_story_ids = {task.user_story_id for task in filtered_tasks}
        visible_stories = [
            story for story in stories if story_ok(story) or story.id in task_story_ids
        ]
        if priority is not None:
            visible_stories = [s for s in visible_stories if s.moscow_priority == priority]
        story_ids = {story.id for story in visible_stories}
        filtered_tasks = [task for task in filtered_tasks if task.user_story_id in story_ids]

        tasks_by_story: dict[str, list[StoryTaskDTO]] = {}
        for task in filtered_tasks:
            tasks_by_story.setdefault(task.user_story_id, []).append(_task_dto(task))

        stories_by_epic: dict[str, list[UserStoryDTO]] = {}
        for story in visible_stories:
            stories_by_epic.setdefault(story.epic_id, []).append(_story_dto(story))

        epic_rows = []
        for epic in epics:
            nested = stories_by_epic.get(epic.id, [])
            epic_match = bool(needle) and _contains(epic.name, needle)
            unfiltered = not any((needle, priority, label, assignee))
            if nested or epic_match or unfiltered:
                epic_rows.append(EpicWithStoriesDTO(epic=_epic_dto(epic), stories=nested))

        filters_on = any((needle, query.priority, assignee, label))
        message = None
        if not epic_rows:
            message = messages.BACKLOG_FILTER_EMPTY if filters_on else messages.BACKLOG_EMPTY
        return BacklogTreeDTO(epics=epic_rows, tasks_by_story=tasks_by_story, message=message)


class CreateEpicUseCase:
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
        self, project_id: str, cmd: CreateEpicCommand, actor: CurrentUser
    ) -> tuple[EpicDTO, MessageResponse]:
        project = _require_project(self._projects, project_id)
        if not can_manage_backlog_structure(actor, project):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_epic_name(cmd.name))
        fields.update(validate_epic_description(cmd.description))
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        epic = Epic(
            id=self._id_gen.generate(),
            project_id=project_id,
            name=cmd.name.strip(),
            description=(cmd.description or "").strip(),
            color=cmd.color,
            sort_order=self._backlog.next_epic_sort_order(project_id),
            created_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        with self._uow:
            self._backlog.save_epic(epic)
            self._uow.commit()
        return _epic_dto(epic), MessageResponse(message=messages.EPIC_CREATED)


class UpdateEpicUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self, epic_id: str, cmd: UpdateEpicCommand, actor: CurrentUser
    ) -> tuple[EpicDTO, MessageResponse]:
        epic = self._backlog.get_epic(epic_id)
        if epic is None:
            raise AppError("EPIC_NOT_FOUND", messages.EPIC_NOT_FOUND, ErrorKind.NOT_FOUND)
        project = _require_project(self._projects, epic.project_id)
        if not can_manage_backlog_structure(actor, project):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_epic_name(cmd.name))
        fields.update(validate_epic_description(cmd.description))
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        epic.name = cmd.name.strip()
        epic.description = (cmd.description or "").strip()
        epic.color = cmd.color
        epic.updated_at = now
        with self._uow:
            self._backlog.update_epic(epic)
            self._uow.commit()
        return _epic_dto(epic), MessageResponse(message=messages.EPIC_UPDATED)


class CreateUserStoryUseCase:
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
        self, epic_id: str, cmd: CreateUserStoryCommand, actor: CurrentUser
    ) -> tuple[UserStoryDTO, MessageResponse]:
        epic = self._backlog.get_epic(epic_id)
        if epic is None:
            raise AppError("EPIC_NOT_FOUND", messages.EPIC_NOT_FOUND, ErrorKind.NOT_FOUND)
        project = _require_project(self._projects, epic.project_id)
        if not can_manage_backlog_structure(actor, project):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_story_title(cmd.title))
        fields.update(validate_story_role(cmd.user_role))
        fields.update(validate_story_reason(cmd.reason))
        if parse_moscow(cmd.moscow_priority.value) is None:
            fields["moscow_priority"] = "Prioridad MoSCoW no válida."
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        story = UserStory(
            id=self._id_gen.generate(),
            epic_id=epic_id,
            project_id=epic.project_id,
            title=cmd.title.strip(),
            user_role=cmd.user_role.strip(),
            reason=cmd.reason.strip(),
            acceptance_criteria=(cmd.acceptance_criteria or "").strip(),
            moscow_priority=cmd.moscow_priority,
            story_points=None,
            estimation_mode=cmd.estimation_mode,
            sprint_id=None,
            sort_order=self._backlog.next_story_sort_order(epic_id),
            created_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        with self._uow:
            self._backlog.save_user_story(story)
            self._uow.commit()
        return _story_dto(story), MessageResponse(message=messages.STORY_CREATED)


class UpdateUserStoryUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self, story_id: str, cmd: UpdateUserStoryCommand, actor: CurrentUser
    ) -> tuple[UserStoryDTO, MessageResponse]:
        story = self._backlog.get_user_story(story_id)
        if story is None:
            raise AppError("STORY_NOT_FOUND", messages.STORY_NOT_FOUND, ErrorKind.NOT_FOUND)
        project = _require_project(self._projects, story.project_id)
        if not can_manage_backlog_structure(actor, project):
            raise AccessDeniedError()

        target_epic = self._backlog.get_epic(cmd.epic_id)
        if target_epic is None or target_epic.project_id != story.project_id:
            raise AppError("EPIC_NOT_FOUND", messages.EPIC_NOT_FOUND, ErrorKind.NOT_FOUND)

        fields: dict[str, str] = {}
        fields.update(validate_story_title(cmd.title))
        fields.update(validate_story_role(cmd.user_role))
        fields.update(validate_story_reason(cmd.reason))
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        story.title = cmd.title.strip()
        story.user_role = cmd.user_role.strip()
        story.reason = cmd.reason.strip()
        story.acceptance_criteria = (cmd.acceptance_criteria or "").strip()
        story.moscow_priority = cmd.moscow_priority
        story.epic_id = cmd.epic_id
        story.updated_at = now
        with self._uow:
            self._backlog.update_user_story(story)
            self._uow.commit()
        return _story_dto(story), MessageResponse(message=messages.STORY_UPDATED)


class AssignStoryPointsUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self, story_id: str, cmd: AssignStoryPointsCommand, actor: CurrentUser
    ) -> tuple[UserStoryDTO, MessageResponse]:
        story = self._backlog.get_user_story(story_id)
        if story is None:
            raise AppError("STORY_NOT_FOUND", messages.STORY_NOT_FOUND, ErrorKind.NOT_FOUND)
        project = _require_project(self._projects, story.project_id)
        if not can_manage_backlog_structure(actor, project):
            raise AccessDeniedError()

        if story.estimation_mode == EstimationMode.TASK:
            raise _validation_error({"story_points": messages.STORY_POINTS_BY_TASK_MODE})

        fields = validate_story_points(cmd.story_points)
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        story.story_points = cmd.story_points
        story.updated_at = now
        with self._uow:
            self._backlog.update_user_story(story)
            self._uow.commit()
        return _story_dto(story), MessageResponse(message=messages.STORY_POINTS_ASSIGNED)


class AssignTaskStoryPointsUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self, task_id: str, cmd: AssignTaskStoryPointsCommand, actor: CurrentUser
    ) -> tuple[StoryTaskDTO, MessageResponse]:
        task = self._backlog.get_story_task(task_id)
        if task is None:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        story = self._backlog.get_user_story(task.user_story_id)
        if story is None:
            raise AppError("STORY_NOT_FOUND", messages.STORY_NOT_FOUND, ErrorKind.NOT_FOUND)
        project = _require_project(self._projects, task.project_id)
        if not can_manage_backlog_structure(actor, project):
            raise AccessDeniedError()

        if story.estimation_mode == EstimationMode.STORY:
            raise _validation_error({"story_points": messages.TASK_POINTS_BY_STORY_MODE})

        fields = validate_story_points(cmd.story_points)
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        task.story_points = cmd.story_points
        task.updated_at = now
        with self._uow:
            self._backlog.update_story_task(task)
            self._uow.commit()
        return _task_dto(task), MessageResponse(message=messages.STORY_POINTS_ASSIGNED)


class CreateStoryTaskUseCase:
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
        self, story_id: str, cmd: CreateStoryTaskCommand, actor: CurrentUser
    ) -> tuple[StoryTaskDTO, MessageResponse]:
        story = self._backlog.get_user_story(story_id)
        if story is None:
            raise AppError("STORY_NOT_FOUND", messages.STORY_NOT_FOUND, ErrorKind.NOT_FOUND)
        project = _require_project(self._projects, story.project_id)
        if not can_manage_story_tasks(actor, project, self._projects):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_task_name(cmd.name))
        if parse_task_type(cmd.task_type.value) is None:
            fields["task_type"] = "Tipo de tarea no válido."
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        task = StoryTask(
            id=self._id_gen.generate(),
            user_story_id=story_id,
            project_id=story.project_id,
            name=cmd.name.strip(),
            task_type=cmd.task_type,
            notes=(cmd.notes or "").strip(),
            status=StoryTaskStatus.TODO,
            assignee_id=None,
            estimated_hours=None,
            created_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        with self._uow:
            self._backlog.save_story_task(task)
            self._uow.commit()
        return _task_dto(task), MessageResponse(message=messages.TASK_ADDED)


class UpdateStoryTaskUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self, task_id: str, cmd: UpdateStoryTaskCommand, actor: CurrentUser
    ) -> tuple[StoryTaskDTO, MessageResponse]:
        task = self._backlog.get_story_task(task_id)
        if task is None:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        project = _require_project(self._projects, task.project_id)
        if not can_manage_story_tasks(actor, project, self._projects):
            raise AccessDeniedError()

        fields: dict[str, str] = {}
        fields.update(validate_task_name(cmd.name))
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        task.name = cmd.name.strip()
        task.task_type = cmd.task_type
        task.notes = (cmd.notes or "").strip()
        task.updated_at = now
        with self._uow:
            self._backlog.update_story_task(task)
            self._uow.commit()
        return _task_dto(task), MessageResponse(message=messages.TASK_UPDATED)


class DeleteStoryTaskUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._uow = uow

    def execute(self, task_id: str, actor: CurrentUser) -> MessageResponse:
        task = self._backlog.get_story_task(task_id)
        if task is None:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        project = _require_project(self._projects, task.project_id)
        if not can_manage_story_tasks(actor, project, self._projects):
            raise AccessDeniedError()

        with self._uow:
            self._backlog.delete_story_task(task_id)
            self._uow.commit()
        return MessageResponse(message=messages.TASK_DELETED)


class AssignStoryTaskUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        members: ActiveMemberLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._members = members
        self._clock = clock
        self._uow = uow

    def execute(
        self, task_id: str, cmd: AssignStoryTaskCommand, actor: CurrentUser
    ) -> tuple[StoryTaskDTO, MessageResponse]:
        task = self._backlog.get_story_task(task_id)
        if task is None:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        project = _require_project(self._projects, task.project_id)
        if not can_manage_story_tasks(actor, project, self._projects):
            raise AccessDeniedError()

        if cmd.assignee_id is not None and not self._members.is_active_project_member(
            task.project_id, cmd.assignee_id
        ):
            raise AppError(
                "ASSIGNEE_NOT_IN_PROJECT",
                messages.ASSIGNEE_NOT_IN_PROJECT,
                ErrorKind.VALIDATION,
                {"assignee_id": messages.ASSIGNEE_NOT_IN_PROJECT},
            )

        now = self._clock.now()
        task.assignee_id = cmd.assignee_id
        task.updated_at = now
        with self._uow:
            self._backlog.update_story_task(task)
            self._uow.commit()
        return _task_dto(task), MessageResponse(message=messages.ASSIGNEE_ASSIGNED)


class UpdateStoryTaskEstimatedHoursUseCase:
    def __init__(
        self,
        backlog: BacklogRepository,
        projects: ProjectLookupPort,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._backlog = backlog
        self._projects = projects
        self._clock = clock
        self._uow = uow

    def execute(
        self, task_id: str, cmd: UpdateEstimatedHoursCommand, actor: CurrentUser
    ) -> tuple[StoryTaskDTO, MessageResponse]:
        task = self._backlog.get_story_task(task_id)
        if task is None:
            raise AppError(
                "STORY_TASK_NOT_FOUND", messages.STORY_TASK_NOT_FOUND, ErrorKind.NOT_FOUND
            )
        project = _require_project(self._projects, task.project_id)
        if not can_manage_story_tasks(actor, project, self._projects):
            raise AccessDeniedError()

        hours = cmd.estimated_hours
        if hours is not None:
            hours = Decimal(hours)
        fields = validate_estimated_hours(hours)
        if fields:
            raise _validation_error(fields)

        now = self._clock.now()
        task.estimated_hours = hours
        task.updated_at = now
        with self._uow:
            self._backlog.update_story_task(task)
            self._uow.commit()
        return _task_dto(task), MessageResponse(message=messages.ESTIMATED_HOURS_SAVED)
