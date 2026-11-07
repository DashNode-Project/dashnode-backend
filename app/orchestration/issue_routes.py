"""Orchestration router for EP-11 Issues and Evidences.

@sad AD-07, AD-08
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
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

from app.modules.auth.infrastructure.models import UserModel
from app.modules.fixes.application.dtos import (
    CreateIssueCommand,
    EvidenceOperationResponse,
    IssueDetailDTO,
    IssueListResponse,
    IssueOperationResponse,
)
from app.modules.fixes.application.use_cases import (
    AttachEvidenceUseCase,
    CreateIssueUseCase,
    DownloadEvidenceUseCase,
    GetIssueDetailUseCase,
    ListIssuesUseCase,
)
from app.modules.fixes.domain.messages import (
    EVIDENCE_NOT_FOUND,
    ISSUE_NOT_FOUND,
    NOT_MEMBER_ERROR,
    SIGNATURE_INVALID_OR_EXPIRED,
)
from app.modules.fixes.infrastructure.repositories import (
    HmacSignedUrlGenerator,
    LocalEvidenceFileStorage,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFixRepository,
)
from app.modules.notifications.infrastructure.models import NotificationModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(tags=["issues"])
_clock = SystemClock()
_id_gen = UuidGenerator()
_storage = LocalEvidenceFileStorage()
_signed_url_gen = HmacSignedUrlGenerator()


class SqlAlchemyUserLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        return (user.name or "").strip(), user.avatar_key


class SqlAlchemyProjectLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_active_member(self, project_id: str, user_id: str) -> bool:
        project = self._session.get(ProjectModel, project_id)
        if project is None:
            return False
        user = self._session.get(UserModel, user_id)
        if user is None or not user.is_active:
            return False
        # Admin has global project access
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_val in ("admin", "administrador"):
            return True
        # Manager of the project
        if project.manager_id == user_id:
            return True
        # Member of the project
        member = self._session.get(ProjectMemberModel, (project_id, user_id))
        return member is not None


class SqlAlchemyIssueNotificationSender:
    def __init__(self, session: Session) -> None:
        self._session = session

    def notify_issue_created(
        self,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
    ) -> None:
        project = self._session.get(ProjectModel, project_id)
        if project is None:
            return

        recipients: set[str] = set()
        if project.manager_id and project.manager_id != reporter_id:
            recipients.add(project.manager_id)

        # Notify project members
        members = (
            self._session.query(ProjectMemberModel.user_id)
            .filter(ProjectMemberModel.project_id == project_id)
            .all()
        )
        for (m_id,) in members:
            if m_id != reporter_id:
                recipients.add(m_id)

        now = _clock.now()
        for r_id in recipients:
            notif = NotificationModel(
                id=_id_gen.generate(),
                recipient_id=r_id,
                type="issue_created",
                title="Nuevo Fix creado",
                message=f"Se ha registrado el issue: {title}",
                is_read=False,
                created_at=now,
            )
            self._session.add(notif)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()


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
    except PermissionError as e:
        raise AppError("FORBIDDEN", str(e), ErrorKind.FORBIDDEN) from e
    except ValueError as e:
        raise AppError("VALIDATION_ERROR", str(e), ErrorKind.VALIDATION) from e


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
) -> IssueListResponse:
    use_case = ListIssuesUseCase(
        repo=repo,
        projects=projects,
        users=users,
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
    except PermissionError as e:
        raise AppError("FORBIDDEN", str(e), ErrorKind.FORBIDDEN) from e
    except ValueError as e:
        raise AppError("VALIDATION_ERROR", str(e), ErrorKind.VALIDATION) from e


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
) -> IssueDetailDTO:
    use_case = GetIssueDetailUseCase(
        issue_repo=repo,
        evidence_repo=evidence_repo,
        signed_url_gen=_signed_url_gen,
        projects=projects,
        users=users,
    )
    try:
        return use_case.execute(project_id=project_id, issue_id=issue_id, actor=actor)
    except PermissionError as e:
        raise AppError("FORBIDDEN", str(e), ErrorKind.FORBIDDEN) from e
    except LookupError as e:
        raise AppError("NOT_FOUND", str(e), ErrorKind.NOT_FOUND) from e


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
    except PermissionError as e:
        raise AppError("FORBIDDEN", str(e), ErrorKind.FORBIDDEN) from e
    except LookupError as e:
        raise AppError("NOT_FOUND", str(e), ErrorKind.NOT_FOUND) from e
    except ValueError as e:
        # Check duplicate
        if "idéntica" in str(e):
            raise AppError("DUPLICATE_EVIDENCE", str(e), ErrorKind.CONFLICT) from e
        raise AppError("VALIDATION_ERROR", str(e), ErrorKind.VALIDATION) from e


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
    except PermissionError as e:
        raise AppError("FORBIDDEN", str(e), ErrorKind.FORBIDDEN) from e
    except LookupError as e:
        raise AppError("NOT_FOUND", str(e), ErrorKind.NOT_FOUND) from e
