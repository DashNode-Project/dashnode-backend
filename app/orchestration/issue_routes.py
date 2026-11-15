"""Orchestration router for EP-11 Issues and Evidences.

@sad AD-07, AD-08
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.modules.fixes.application.dtos import (
    AssignIssueCommand,
    CloseIssueCommand,
    CreateIssueCommand,
    EvidenceOperationResponse,
    IssueDetailDTO,
    IssueListResponse,
    IssueOperationResponse,
    ReportTaskFixCommand,
    ResolveIssueCommand,
)
from app.modules.fixes.application.use_cases import (
    AssignIssueUseCase,
    AttachEvidenceUseCase,
    CloseIssueUseCase,
    CreateIssueUseCase,
    DownloadEvidenceUseCase,
    GetIssueDetailUseCase,
    ListIssuesUseCase,
    ReportTaskFixUseCase,
    ResolveIssueUseCase,
)
from app.modules.fixes.domain.entities import ConflictError
from app.modules.fixes.infrastructure.repositories import (
    HmacSignedUrlGenerator,
    LocalEvidenceFileStorage,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFixRepository,
)
from app.orchestration.fixes_adapters import (
    SqlAlchemyFixTaskCoordinator,
    SqlAlchemyIssueNotificationSender,
    SqlAlchemyProjectLookup,
    SqlAlchemyUserLookup,
)
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator
from app.shared.infrastructure.outbox import SqlAlchemyOutboxStore

router = APIRouter(tags=["issues"])
_clock = SystemClock()
_id_gen = UuidGenerator()
_storage = LocalEvidenceFileStorage()
_signed_url_gen = HmacSignedUrlGenerator()


def _fix_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyFixRepository:
    return SqlAlchemyFixRepository(db)


def _evidence_repo(db: Session = Depends(get_db_session)) -> SqlAlchemyEvidenceRepository:
    return SqlAlchemyEvidenceRepository(db)


def _project_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyProjectLookup:
    return SqlAlchemyProjectLookup(db)


def _user_lookup(db: Session = Depends(get_db_session)) -> SqlAlchemyUserLookup:
    return SqlAlchemyUserLookup(db)


def _notif_sender(db: Session = Depends(get_db_session)) -> SqlAlchemyIssueNotificationSender:
    return SqlAlchemyIssueNotificationSender(db)


def _task_coordinator(db: Session = Depends(get_db_session)) -> SqlAlchemyFixTaskCoordinator:
    return SqlAlchemyFixTaskCoordinator(db)


def _outbox_store(db: Session = Depends(get_db_session)) -> SqlAlchemyOutboxStore:
    return SqlAlchemyOutboxStore(db)


def _translate_issue_error(exc: Exception) -> AppError:
    if isinstance(exc, PermissionError):
        return AppError("FORBIDDEN", str(exc), ErrorKind.FORBIDDEN)
    if isinstance(exc, LookupError):
        return AppError("NOT_FOUND", str(exc), ErrorKind.NOT_FOUND)
    if isinstance(exc, ConflictError):
        return AppError("CONFLICT", str(exc), ErrorKind.CONFLICT)
    if isinstance(exc, ValueError):
        if "idéntica" in str(exc):
            return AppError("DUPLICATE_EVIDENCE", str(exc), ErrorKind.CONFLICT)
        return AppError("VALIDATION_ERROR", str(exc), ErrorKind.VALIDATION)
    return AppError(
        "INTERNAL_ERROR",
        "No fue posible completar la operación. Intente nuevamente.",
        ErrorKind.UNAVAILABLE,
    )


@router.post(
    "/projects/{project_id}/issues",
    response_model=IssueOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un issue (Fix) en un proyecto",
)
def create_issue(
    project_id: str,
    cmd: CreateIssueCommand,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    notifications: SqlAlchemyIssueNotificationSender = Depends(_notif_sender),
) -> IssueOperationResponse:
    if idempotency_key:
        cmd.idempotency_key = idempotency_key

    use_case = CreateIssueUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
        notification_sender=notifications,
    )
    try:
        return use_case.execute(project_id=project_id, cmd=cmd, actor=actor)
    except (PermissionError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.get(
    "/projects/{project_id}/issues",
    response_model=IssueListResponse,
    summary="Consultar y filtrar la lista de issues de un proyecto",
)
def list_issues(
    project_id: str,
    status: str | None = Query(None),
    severity: str | None = Query(None),
    type: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    actor: CurrentUser = Depends(get_current_user),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    tasks: SqlAlchemyFixTaskCoordinator = Depends(_task_coordinator),
) -> IssueListResponse:
    use_case = ListIssuesUseCase(
        repo=repo,
        projects=projects,
        users=users,
        tasks=tasks,
    )
    try:
        return use_case.execute(
            project_id=project_id,
            actor=actor,
            status=status,
            severity=severity,
            issue_type=type,
            cursor=cursor,
            limit=limit,
        )
    except (PermissionError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.get(
    "/projects/{project_id}/issues/{issue_id}",
    response_model=IssueDetailDTO,
    summary="Consultar el detalle de un issue",
)
def get_issue_detail(
    project_id: str,
    issue_id: str,
    actor: CurrentUser = Depends(get_current_user),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    evidence_repo: SqlAlchemyEvidenceRepository = Depends(_evidence_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    tasks: SqlAlchemyFixTaskCoordinator = Depends(_task_coordinator),
) -> IssueDetailDTO:
    use_case = GetIssueDetailUseCase(
        issue_repo=repo,
        evidence_repo=evidence_repo,
        signed_url_gen=_signed_url_gen,
        projects=projects,
        users=users,
        tasks=tasks,
    )
    try:
        return use_case.execute(project_id=project_id, issue_id=issue_id, actor=actor)
    except (PermissionError, LookupError) as exc:
        raise _translate_issue_error(exc) from exc


@router.patch(
    "/projects/{project_id}/issues/{issue_id}/assignee",
    response_model=IssueOperationResponse,
    summary="Asignar issue a desarrollador miembro del proyecto (HU_DN_07_102)",
)
def assign_issue(
    project_id: str,
    issue_id: str,
    cmd: AssignIssueCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    notifications: SqlAlchemyIssueNotificationSender = Depends(_notif_sender),
    tasks: SqlAlchemyFixTaskCoordinator = Depends(_task_coordinator),
    outbox: SqlAlchemyOutboxStore = Depends(_outbox_store),
) -> IssueOperationResponse:
    use_case = AssignIssueUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
        outbox=outbox,
        notification_sender=notifications,
        tasks=tasks,
    )
    try:
        return use_case.execute(project_id=project_id, issue_id=issue_id, cmd=cmd, actor=actor)
    except (PermissionError, LookupError, ConflictError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.post(
    "/projects/{project_id}/issues/{issue_id}/resolve",
    response_model=IssueOperationResponse,
    summary="Resolver issue con nota de resolución y actualizar tarea vinculada",
)
def resolve_issue(
    project_id: str,
    issue_id: str,
    cmd: ResolveIssueCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    notifications: SqlAlchemyIssueNotificationSender = Depends(_notif_sender),
    tasks: SqlAlchemyFixTaskCoordinator = Depends(_task_coordinator),
    outbox: SqlAlchemyOutboxStore = Depends(_outbox_store),
) -> IssueOperationResponse:
    use_case = ResolveIssueUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
        outbox=outbox,
        tasks=tasks,
        notification_sender=notifications,
    )
    try:
        return use_case.execute(project_id=project_id, issue_id=issue_id, cmd=cmd, actor=actor)
    except (PermissionError, LookupError, ConflictError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.post(
    "/projects/{project_id}/issues/{issue_id}/close",
    response_model=IssueOperationResponse,
    summary="Cerrar un issue resuelto (Administrador o Gerente)",
)
def close_issue(
    project_id: str,
    issue_id: str,
    cmd: CloseIssueCommand,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    tasks: SqlAlchemyFixTaskCoordinator = Depends(_task_coordinator),
    outbox: SqlAlchemyOutboxStore = Depends(_outbox_store),
) -> IssueOperationResponse:
    use_case = CloseIssueUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
        outbox=outbox,
        tasks=tasks,
    )
    try:
        return use_case.execute(project_id=project_id, issue_id=issue_id, cmd=cmd, actor=actor)
    except (PermissionError, LookupError, ConflictError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.post(
    "/projects/{project_id}/tasks/{task_id}/report-fix",
    response_model=IssueOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reportar un fix desde una tarea y moverla atómicamente a Corrección",
)
def report_task_fix(
    project_id: str,
    task_id: str,
    cmd: ReportTaskFixCommand,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
    notifications: SqlAlchemyIssueNotificationSender = Depends(_notif_sender),
    tasks: SqlAlchemyFixTaskCoordinator = Depends(_task_coordinator),
    outbox: SqlAlchemyOutboxStore = Depends(_outbox_store),
) -> IssueOperationResponse:
    if idempotency_key:
        cmd.idempotency_key = idempotency_key

    use_case = ReportTaskFixUseCase(
        repo=repo,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
        tasks=tasks,
        outbox=outbox,
        notification_sender=notifications,
    )
    try:
        return use_case.execute(
            project_id=project_id,
            task_id=task_id,
            cmd=cmd,
            actor=actor,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.post(
    "/projects/{project_id}/issues/{issue_id}/evidences",
    response_model=EvidenceOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Asociar evidencia a un issue",
)
async def attach_evidence(
    project_id: str,
    issue_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    repo: SqlAlchemyFixRepository = Depends(_fix_repo),
    evidence_repo: SqlAlchemyEvidenceRepository = Depends(_evidence_repo),
    projects: SqlAlchemyProjectLookup = Depends(_project_lookup),
    users: SqlAlchemyUserLookup = Depends(_user_lookup),
) -> EvidenceOperationResponse:
    use_case = AttachEvidenceUseCase(
        issue_repo=repo,
        evidence_repo=evidence_repo,
        storage=_storage,
        signed_url_gen=_signed_url_gen,
        uow=SqlAlchemyUnitOfWork(db),
        id_gen=_id_gen,
        clock=_clock,
        projects=projects,
        users=users,
    )
    raw_data = await file.read()
    filename = file.filename or "evidence"
    try:
        return use_case.execute(
            project_id=project_id,
            issue_id=issue_id,
            file_name=filename,
            raw_data=raw_data,
            title=title,
            actor=actor,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_issue_error(exc) from exc


@router.get(
    "/projects/{project_id}/issues/{issue_id}/evidences/{evidence_id}/content",
    summary="Descargar o visualizar contenido de evidencia con URL firmada",
)
def download_evidence(
    project_id: str,
    issue_id: str,
    evidence_id: str,
    signature: str = Query(...),
    expires: int = Query(...),
    evidence_repo: SqlAlchemyEvidenceRepository = Depends(_evidence_repo),
) -> Response:
    use_case = DownloadEvidenceUseCase(
        evidence_repo=evidence_repo,
        storage=_storage,
        signed_url_gen=_signed_url_gen,
        clock=_clock,
    )
    try:
        data, mime_type, file_name = use_case.execute(
            evidence_id=evidence_id,
            expires=expires,
            signature=signature,
        )
        return Response(
            content=data,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Cache-Control": "private, max-age=300",
            },
        )
    except (PermissionError, LookupError) as exc:
        raise _translate_issue_error(exc) from exc
