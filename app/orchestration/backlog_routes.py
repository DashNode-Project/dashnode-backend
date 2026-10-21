"""Backlog HTTP routes (EP-06)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.modules.backlog.application.dtos import (
    AssignStoryPointsCommand,
    AssignStoryTaskCommand,
    BacklogTreeDTO,
    ChangeTaskStatusCommand,
    ChangeTaskStatusResponse,
    CreateEpicCommand,
    CreateStoryTaskCommand,
    CreateUserStoryCommand,
    EpicDTO,
    LogTaskHoursCommand,
    LogTaskHoursResponse,
    MessageResponse,
    MyTasksResponse,
    StoryTaskDTO,
    UpdateEpicCommand,
    UpdateEstimatedHoursCommand,
    UpdateStoryTaskCommand,
    UpdateUserStoryCommand,
    UserStoryDTO,
)
from app.modules.backlog.application.task_flow import (
    ChangeStoryTaskStatusUseCase,
    ListMyTasksUseCase,
    LogStoryTaskHoursUseCase,
)
from app.modules.backlog.application.use_cases import (
    AssignStoryPointsUseCase,
    AssignStoryTaskUseCase,
    BacklogFilters,
    CreateEpicUseCase,
    CreateStoryTaskUseCase,
    CreateUserStoryUseCase,
    DeleteStoryTaskUseCase,
    GetProjectBacklogUseCase,
    UpdateEpicUseCase,
    UpdateStoryTaskEstimatedHoursUseCase,
    UpdateStoryTaskUseCase,
    UpdateUserStoryUseCase,
)
from app.modules.backlog.infrastructure.repositories import SqlAlchemyBacklogRepository
from app.orchestration.backlog_adapters import (
    SqlAlchemyActiveMemberLookup,
    SqlAlchemyProjectLookup,
)
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(tags=["backlog"])
_clock = SystemClock()
_id_gen = UuidGenerator()


class EpicCreatedResponse(EpicDTO):
    message: str


class EpicUpdatedResponse(EpicDTO):
    message: str


class StoryCreatedResponse(UserStoryDTO):
    message: str


class StoryUpdatedResponse(UserStoryDTO):
    message: str


class StoryPointsResponse(UserStoryDTO):
    message: str


class TaskCreatedResponse(StoryTaskDTO):
    message: str


class TaskUpdatedResponse(StoryTaskDTO):
    message: str


class TaskAssignResponse(StoryTaskDTO):
    message: str


class TaskHoursResponse(StoryTaskDTO):
    message: str


@router.get(
    "/projects/{project_id}/backlog",
    response_model=BacklogTreeDTO,
    summary="Árbol de backlog del proyecto",
)
def get_project_backlog(
    project_id: str,
    q: str | None = Query(default=None, max_length=200),
    priority: str | None = Query(default=None, max_length=32),
    assigned_to: str | None = Query(default=None, alias="assignedTo", max_length=36),
    label: str | None = Query(default=None, max_length=80),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BacklogTreeDTO:
    use_case = GetProjectBacklogUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
    )
    return use_case.execute(
        project_id,
        current_user,
        BacklogFilters(q=q, priority=priority, assigned_to=assigned_to, label=label),
    )


@router.get("/projects/{project_id}/backlog/tree", response_model=BacklogTreeDTO)
def get_project_backlog_tree(
    project_id: str,
    q: str | None = Query(default=None, max_length=200),
    priority: str | None = Query(default=None, max_length=32),
    assigned_to: str | None = Query(default=None, alias="assignedTo", max_length=36),
    label: str | None = Query(default=None, max_length=80),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BacklogTreeDTO:
    use_case = GetProjectBacklogUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
    )
    return use_case.execute(
        project_id,
        current_user,
        BacklogFilters(q=q, priority=priority, assigned_to=assigned_to, label=label),
    )


@router.post(
    "/projects/{project_id}/epics",
    response_model=EpicCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_epic(
    project_id: str,
    cmd: CreateEpicCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> EpicCreatedResponse:
    use_case = CreateEpicUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(project_id, cmd, current_user)
    return EpicCreatedResponse(**dto.model_dump(), message=msg.message)


@router.patch(
    "/epics/{epic_id}",
    response_model=EpicUpdatedResponse,
)
def update_epic(
    epic_id: str,
    cmd: UpdateEpicCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> EpicUpdatedResponse:
    use_case = UpdateEpicUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(epic_id, cmd, current_user)
    return EpicUpdatedResponse(**dto.model_dump(), message=msg.message)


@router.post(
    "/epics/{epic_id}/user-stories",
    response_model=StoryCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_story(
    epic_id: str,
    cmd: CreateUserStoryCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> StoryCreatedResponse:
    use_case = CreateUserStoryUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(epic_id, cmd, current_user)
    return StoryCreatedResponse(**dto.model_dump(), message=msg.message)


@router.patch(
    "/user-stories/{story_id}",
    response_model=StoryUpdatedResponse,
)
def update_user_story(
    story_id: str,
    cmd: UpdateUserStoryCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> StoryUpdatedResponse:
    use_case = UpdateUserStoryUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(story_id, cmd, current_user)
    return StoryUpdatedResponse(**dto.model_dump(), message=msg.message)


@router.patch(
    "/user-stories/{story_id}/story-points",
    response_model=StoryPointsResponse,
)
def assign_story_points(
    story_id: str,
    cmd: AssignStoryPointsCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> StoryPointsResponse:
    use_case = AssignStoryPointsUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(story_id, cmd, current_user)
    return StoryPointsResponse(**dto.model_dump(), message=msg.message)


@router.post(
    "/user-stories/{story_id}/tasks",
    response_model=TaskCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_story_task(
    story_id: str,
    cmd: CreateStoryTaskCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TaskCreatedResponse:
    use_case = CreateStoryTaskUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(story_id, cmd, current_user)
    return TaskCreatedResponse(**dto.model_dump(), message=msg.message)


@router.patch(
    "/story-tasks/{task_id}",
    response_model=TaskUpdatedResponse,
)
def update_story_task(
    task_id: str,
    cmd: UpdateStoryTaskCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TaskUpdatedResponse:
    use_case = UpdateStoryTaskUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(task_id, cmd, current_user)
    return TaskUpdatedResponse(**dto.model_dump(), message=msg.message)


@router.delete(
    "/story-tasks/{task_id}",
    response_model=MessageResponse,
)
def delete_story_task(
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    use_case = DeleteStoryTaskUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(task_id, current_user)


@router.patch(
    "/story-tasks/{task_id}/assignee",
    response_model=TaskAssignResponse,
)
def assign_story_task(
    task_id: str,
    cmd: AssignStoryTaskCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TaskAssignResponse:
    use_case = AssignStoryTaskUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        members=SqlAlchemyActiveMemberLookup(db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(task_id, cmd, current_user)
    return TaskAssignResponse(**dto.model_dump(), message=msg.message)


@router.patch(
    "/story-tasks/{task_id}/estimated-hours",
    response_model=TaskHoursResponse,
)
def update_estimated_hours(
    task_id: str,
    cmd: UpdateEstimatedHoursCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TaskHoursResponse:
    use_case = UpdateStoryTaskEstimatedHoursUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    dto, msg = use_case.execute(task_id, cmd, current_user)
    return TaskHoursResponse(**dto.model_dump(), message=msg.message)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/time-logs",
    response_model=LogTaskHoursResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_task_hours(
    project_id: str,
    task_id: str,
    cmd: LogTaskHoursCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> LogTaskHoursResponse:
    use_case = LogStoryTaskHoursUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, task_id, cmd, current_user)


@router.patch(
    "/projects/{project_id}/tasks/{task_id}/status",
    response_model=ChangeTaskStatusResponse,
)
def change_task_status(
    project_id: str,
    task_id: str,
    cmd: ChangeTaskStatusCommand,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ChangeTaskStatusResponse:
    use_case = ChangeStoryTaskStatusUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, task_id, cmd, current_user)


@router.get("/users/me/tasks", response_model=MyTasksResponse)
def list_my_tasks(
    project_id: str | None = Query(default=None, alias="projectId", max_length=36),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MyTasksResponse:
    use_case = ListMyTasksUseCase(
        backlog=SqlAlchemyBacklogRepository(db),
        projects=SqlAlchemyProjectLookup(db),
    )
    return use_case.execute(current_user, project_id=project_id, status=status_filter)
