"""Kanban HTTP routes (EP-08)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.infrastructure.repositories import SqlAlchemyBacklogRepository
from app.modules.kanban.application.dtos import (
    KanbanBoardResponse,
    UpdateTaskBlockCommand,
    UpdateTaskBlockResponse,
    UpdateWipLimitCommand,
    UpdateWipLimitResponse,
)
from app.modules.kanban.application.use_cases import (
    GetKanbanBoardUseCase,
    UpdateColumnWipLimitUseCase,
    UpdateTaskBlockUseCase,
)
from app.modules.kanban.infrastructure.repositories import SqlAlchemyKanbanRepository
from app.modules.sprints.infrastructure.repositories import SqlAlchemySprintRepository
from app.orchestration.backlog_adapters import SqlAlchemyProjectLookup
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(tags=["kanban"])
_clock = SystemClock()
_id_gen = UuidGenerator()


class SqlAlchemyUserLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        return user.name, user.avatar_key


def _kanban_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyKanbanRepository:
    return SqlAlchemyKanbanRepository(db)


def _sprint_repo(db: Session = Depends(get_db_session)) -> SqlAlchemySprintRepository:
    return SqlAlchemySprintRepository(db)


def _backlog_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyBacklogRepository:
    return SqlAlchemyBacklogRepository(db)


def _project_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyProjectLookup:
    return SqlAlchemyProjectLookup(db)


def _user_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyUserLookup:
    return SqlAlchemyUserLookup(db)


@router.get(
    "/projects/{project_id}/kanban",
    response_model=KanbanBoardResponse,
)
def get_kanban_board(
    project_id: str,
    actor: CurrentUser = Depends(get_current_user),
    sprints: SqlAlchemySprintRepository = Depends(_sprint_repo),
    backlog: SqlAlchemyBacklogRepository = Depends(_backlog_repo),
    kanban: SqlAlchemyKanbanRepository = Depends(_kanban_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> KanbanBoardResponse:
    use_case = GetKanbanBoardUseCase(
        sprints=sprints,
        backlog=backlog,
        kanban=kanban,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, actor)


@router.put(
    "/projects/{project_id}/kanban/columns/{column_id}/wip",
    response_model=UpdateWipLimitResponse,
)
def update_column_wip(
    project_id: str,
    column_id: str,
    cmd: UpdateWipLimitCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    kanban: SqlAlchemyKanbanRepository = Depends(_kanban_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> UpdateWipLimitResponse:
    use_case = UpdateColumnWipLimitUseCase(
        kanban=kanban,
        projects=projects,
        id_gen=_id_gen,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, column_id, cmd, actor)


@router.patch(
    "/projects/{project_id}/tasks/{task_id}/block",
    response_model=UpdateTaskBlockResponse,
)
def update_task_block(
    project_id: str,
    task_id: str,
    cmd: UpdateTaskBlockCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    backlog: SqlAlchemyBacklogRepository = Depends(_backlog_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> UpdateTaskBlockResponse:
    use_case = UpdateTaskBlockUseCase(
        backlog=backlog,
        projects=projects,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(db),
    )
    return use_case.execute(project_id, task_id, cmd, actor)
