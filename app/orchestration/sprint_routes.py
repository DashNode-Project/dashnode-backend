"""Sprint HTTP routes (EP-07)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.modules.backlog.infrastructure.repositories import SqlAlchemyBacklogRepository
from app.modules.sprints.application.dtos import (
    AssignStoryToSprintCommand,
    AssignStoryToSprintResponse,
    CreateSprintCommand,
    CreateSprintResponse,
    CurrentSprintResponse,
    SprintListResponse,
    StartSprintResponse,
)
from app.modules.sprints.application.use_cases import (
    AssignUserStoryToSprintUseCase,
    CreateSprintUseCase,
    GetCurrentSprintUseCase,
    ListProjectSprintsUseCase,
    StartSprintUseCase,
)
from app.modules.sprints.infrastructure.repositories import SqlAlchemySprintRepository
from app.orchestration.backlog_adapters import SqlAlchemyProjectLookup
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(tags=["sprints"])
_clock = SystemClock()
_id_gen = UuidGenerator()


def _sprint_repo(db: Session = Depends(get_db_session)) -> SqlAlchemySprintRepository:
    return SqlAlchemySprintRepository(db)


def _backlog_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyBacklogRepository:
    return SqlAlchemyBacklogRepository(db)


def _project_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyProjectLookup:
    return SqlAlchemyProjectLookup(db)


@router.post(
    "/projects/{project_id}/sprints",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateSprintResponse,
)
def create_sprint(
    project_id: str,
    body: CreateSprintCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> CreateSprintResponse:
    use_case = CreateSprintUseCase(
        sprints=SqlAlchemySprintRepository(db),
        projects=projects,
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, body, actor)


@router.get("/projects/{project_id}/sprints", response_model=SprintListResponse)
def list_sprints(
    project_id: str,
    actor: CurrentUser = Depends(get_current_user),
    sprints: SqlAlchemySprintRepository = Depends(_sprint_repo),
    backlog: SqlAlchemyBacklogRepository = Depends(_backlog_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> SprintListResponse:
    use_case = ListProjectSprintsUseCase(sprints, backlog, projects)
    return use_case.execute(project_id, actor)


@router.get("/projects/{project_id}/sprints/current", response_model=CurrentSprintResponse)
def get_current_sprint(
    project_id: str,
    actor: CurrentUser = Depends(get_current_user),
    sprints: SqlAlchemySprintRepository = Depends(_sprint_repo),
    backlog: SqlAlchemyBacklogRepository = Depends(_backlog_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> CurrentSprintResponse:
    use_case = GetCurrentSprintUseCase(sprints, backlog, projects, _clock)
    return use_case.execute(project_id, actor)


@router.post(
    "/projects/{project_id}/sprints/{sprint_id}/start",
    response_model=StartSprintResponse,
)
def start_sprint(
    project_id: str,
    sprint_id: str,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> StartSprintResponse:
    use_case = StartSprintUseCase(
        sprints=SqlAlchemySprintRepository(db),
        projects=projects,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, sprint_id, actor)


@router.patch(
    "/projects/{project_id}/user-stories/{story_id}/sprint",
    response_model=AssignStoryToSprintResponse,
)
def assign_story_to_sprint(
    project_id: str,
    story_id: str,
    body: AssignStoryToSprintCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    sprints: SqlAlchemySprintRepository = Depends(_sprint_repo),
    backlog: SqlAlchemyBacklogRepository = Depends(_backlog_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> AssignStoryToSprintResponse:
    use_case = AssignUserStoryToSprintUseCase(
        sprints=sprints,
        backlog=backlog,
        projects=projects,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, story_id, body, actor)
