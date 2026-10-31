"""Documentation HTTP routes (EP-09)."""

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.documentation.application.dtos import (
    CreateDocumentationCommand,
    DocumentationEntryDTO,
    DocumentationListResponse,
    DocumentationOperationResponse,
    RejectDocumentationCommand,
    ResubmitDocumentationCommand,
    TogglePinCommand,
    UpdateDocumentationCommand,
    UpdateVisibilityCommand,
)
from app.modules.documentation.application.use_cases import (
    ApproveDocumentationEntryUseCase,
    CreateDocumentationEntryUseCase,
    DeleteDocumentationEntryUseCase,
    GetDocumentationEntryUseCase,
    ListDocumentationEntriesUseCase,
    ListPendingDocumentationEntriesUseCase,
    RejectDocumentationEntryUseCase,
    ResubmitDocumentationEntryUseCase,
    ToggleDocumentationPinUseCase,
    ToggleDocumentationVisibilityUseCase,
    UpdateDocumentationEntryUseCase,
)
from app.modules.documentation.infrastructure.repositories import (
    SqlAlchemyDocumentationRepository,
)
from app.orchestration.backlog_adapters import SqlAlchemyProjectLookup
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(tags=["documentation"])
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


def _doc_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyDocumentationRepository:
    return SqlAlchemyDocumentationRepository(db)


def _project_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyProjectLookup:
    return SqlAlchemyProjectLookup(db)


def _user_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyUserLookup:
    return SqlAlchemyUserLookup(db)


@router.post(
    "/projects/{project_id}/documentation",
    response_model=DocumentationOperationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_documentation_entry(
    project_id: str,
    cmd: CreateDocumentationCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = CreateDocumentationEntryUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, cmd, actor)


@router.get(
    "/projects/{project_id}/documentation",
    response_model=DocumentationListResponse,
)
def list_documentation_entries(
    project_id: str,
    category: str | None = Query(None),
    approval_status: str | None = Query(None),
    search: str | None = Query(None),
    actor: CurrentUser = Depends(get_current_user),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationListResponse:
    use_case = ListDocumentationEntriesUseCase(
        repo=repo,
        projects=projects,
        users=users,
    )
    return use_case.execute(
        project_id=project_id,
        actor=actor,
        category=category,
        approval_status=approval_status,
        search=search,
    )


@router.get(
    "/projects/{project_id}/documentation/pending-approvals",
    response_model=DocumentationListResponse,
)
@router.get(
    "/projects/{project_id}/documentation/pending",
    response_model=DocumentationListResponse,
)
def list_pending_documentation_entries(
    project_id: str,
    actor: CurrentUser = Depends(get_current_user),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationListResponse:
    use_case = ListPendingDocumentationEntriesUseCase(
        repo=repo,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, actor)


@router.get(
    "/projects/{project_id}/documentation/{entry_id}",
    response_model=DocumentationEntryDTO,
)
def get_documentation_entry(
    project_id: str,
    entry_id: str,
    actor: CurrentUser = Depends(get_current_user),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationEntryDTO:
    use_case = GetDocumentationEntryUseCase(
        repo=repo,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, actor)


@router.put(
    "/projects/{project_id}/documentation/{entry_id}",
    response_model=DocumentationOperationResponse,
)
def update_documentation_entry(
    project_id: str,
    entry_id: str,
    cmd: UpdateDocumentationCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = UpdateDocumentationEntryUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, cmd, actor)


@router.delete(
    "/projects/{project_id}/documentation/{entry_id}",
    response_model=DocumentationOperationResponse,
)
def delete_documentation_entry(
    project_id: str,
    entry_id: str,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
) -> DocumentationOperationResponse:
    use_case = DeleteDocumentationEntryUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        clock=_clock,
        projects=projects,
    )
    return use_case.execute(project_id, entry_id, actor)


@router.patch(
    "/projects/{project_id}/documentation/{entry_id}/visibility",
    response_model=DocumentationOperationResponse,
)
def toggle_documentation_visibility(
    project_id: str,
    entry_id: str,
    cmd: UpdateVisibilityCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = ToggleDocumentationVisibilityUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, cmd, actor)


@router.post(
    "/projects/{project_id}/documentation/{entry_id}/approve",
    response_model=DocumentationOperationResponse,
)
def approve_documentation_entry(
    project_id: str,
    entry_id: str,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = ApproveDocumentationEntryUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, actor)


@router.post(
    "/projects/{project_id}/documentation/{entry_id}/reject",
    response_model=DocumentationOperationResponse,
)
def reject_documentation_entry(
    project_id: str,
    entry_id: str,
    cmd: RejectDocumentationCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = RejectDocumentationEntryUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, cmd, actor)


@router.post(
    "/projects/{project_id}/documentation/{entry_id}/resubmit",
    response_model=DocumentationOperationResponse,
)
def resubmit_documentation_entry(
    project_id: str,
    entry_id: str,
    cmd: ResubmitDocumentationCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = ResubmitDocumentationEntryUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, cmd, actor)


@router.patch(
    "/projects/{project_id}/documentation/{entry_id}/pin",
    response_model=DocumentationOperationResponse,
)
@router.post(
    "/projects/{project_id}/documentation/{entry_id}/pin",
    response_model=DocumentationOperationResponse,
)
def toggle_documentation_pin(
    project_id: str,
    entry_id: str,
    cmd: TogglePinCommand | None = Body(default=None),
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyDocumentationRepository = Depends(_doc_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> DocumentationOperationResponse:
    use_case = ToggleDocumentationPinUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
    )
    return use_case.execute(project_id, entry_id, cmd, actor)
