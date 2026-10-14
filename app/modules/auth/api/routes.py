"""
FastAPI router for Authentication module.
Complies strictly with BR-1 (no direct DB/infrastructure imports).
@sad 4.1.1, AD-08
@origin [SAD-Propuesto]
"""

from fastapi import APIRouter, Depends, Query, Response, status

from app.config import settings
from app.modules.auth.application.dtos import (
    AdminDashboardSummaryDTO,
    AdminUserSummaryDTO,
    CompletePasswordResetCommand,
    CreateUserByAdminCommand,
    InviteDeveloperCommand,
    InviteDeveloperResponse,
    LoginCommand,
    LogoutResponse,
    ManagerDeveloperSummaryDTO,
    MessageResponse,
    RegisterManagerCommand,
    RegisterManagerResponse,
    RequestPasswordResetCommand,
    SessionInfo,
)
from app.modules.auth.application.password_reset_use_cases import (
    AdminRequestPasswordResetUseCase,
    CompletePasswordResetUseCase,
    RequestPasswordResetUseCase,
)
from app.modules.auth.application.session_use_cases import LoginUseCase, LogoutUseCase
from app.modules.auth.application.use_cases import RegisterManagerUseCase
from app.modules.auth.application.user_administration_use_cases import (
    CreateUserByAdminUseCase,
    DeactivateDeveloperByManagerUseCase,
    GetAdminDashboardSummaryUseCase,
    InviteDeveloperByManagerUseCase,
    ListActiveManagersUseCase,
    ListActiveUsersUseCase,
    ListAdminUsersUseCase,
    ListManagerDevelopersUseCase,
    ReactivateDeveloperByManagerUseCase,
)
from app.orchestration.auth_container import (
    get_admin_dashboard_summary_use_case,
    get_admin_request_password_reset_use_case,
    get_complete_password_reset_use_case,
    get_create_user_by_admin_use_case,
    get_deactivate_developer_by_manager_use_case,
    get_invite_developer_use_case,
    get_list_active_managers_use_case,
    get_list_active_users_use_case,
    get_list_admin_users_use_case,
    get_list_manager_developers_use_case,
    get_login_use_case,
    get_logout_use_case,
    get_reactivate_developer_by_manager_use_case,
    get_register_manager_use_case,
    get_request_password_reset_use_case,
)
from app.orchestration.security import (
    get_current_session,
    get_session_token,
    require_admin,
    require_admin_or_manager,
    require_manager,
)
from app.shared.application.identity import CurrentSession, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterManagerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una cuenta con rol Gerente (publico)",
)
def register(
    cmd: RegisterManagerCommand,
    use_case: RegisterManagerUseCase = Depends(get_register_manager_use_case),
) -> RegisterManagerResponse:
    return use_case.execute(cmd)


@router.post(
    "/login",
    response_model=SessionInfo,
    summary="Iniciar sesion: abre una sesion de servidor y la entrega en cookie HttpOnly",
)
def login(
    cmd: LoginCommand,
    response: Response,
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> SessionInfo:
    result = use_case.execute(cmd)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=result.token,
        max_age=settings.session_cookie_max_age_seconds,
        path="/",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    return result.session


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Cerrar sesion: invalida la sesion en el servidor y elimina la cookie",
)
def logout(
    response: Response,
    token: str | None = Depends(get_session_token),
    use_case: LogoutUseCase = Depends(get_logout_use_case),
) -> LogoutResponse:
    result = use_case.execute(token)
    # Only reached when the session was invalidated: a technical failure raises before.
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    return result


@router.get(
    "/session",
    response_model=CurrentSession,
    summary="Validar la sesion actual (HttpOnly cookie) y obtener usuario y vigencia",
    responses={
        401: {"description": "NOT_AUTHENTICATED o SESSION_EXPIRED (la cookie se elimina)"},
        403: {"description": "ACCOUNT_DISABLED"},
    },
)
def get_session(session: CurrentSession = Depends(get_current_session)) -> CurrentSession:
    """Lets the SPA restore the authenticated state after a page reload (HU_DN_01_05).

    Read-only: it never renews the session, the 8 hours are counted from login.
    """
    return session


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Solicitar enlace de restablecimiento (respuesta agnostica)",
)
def request_password_reset(
    cmd: RequestPasswordResetCommand,
    use_case: RequestPasswordResetUseCase = Depends(get_request_password_reset_use_case),
) -> MessageResponse:
    return use_case.execute(cmd)


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Establecer contrasena con enlace de un solo uso",
)
def confirm_password_reset(
    cmd: CompletePasswordResetCommand,
    use_case: CompletePasswordResetUseCase = Depends(get_complete_password_reset_use_case),
) -> MessageResponse:
    return use_case.execute(cmd)


@router.get(
    "/admin/dashboard-summary",
    response_model=AdminDashboardSummaryDTO,
    summary="Métricas de inicio del administrador",
)
def admin_dashboard_summary(
    current_user: CurrentUser = Depends(require_admin),
    use_case: GetAdminDashboardSummaryUseCase = Depends(get_admin_dashboard_summary_use_case),
) -> AdminDashboardSummaryDTO:
    return use_case.execute(actor_id=current_user.id)


@router.get(
    "/admin/users",
    response_model=list[AdminUserSummaryDTO],
    summary="Listar usuarios (solo Administrador)",
)
def list_admin_users(
    name: str | None = Query(default=None, max_length=200),
    role: str | None = Query(default=None, max_length=50),
    current_user: CurrentUser = Depends(require_admin),
    use_case: ListAdminUsersUseCase = Depends(get_list_admin_users_use_case),
) -> list[AdminUserSummaryDTO]:
    return use_case.execute(actor_id=current_user.id, name=name, role=role)


@router.get(
    "/managers",
    response_model=list[AdminUserSummaryDTO],
    summary="Listar gerentes activos (Administrador o Gerente)",
)
def list_active_managers(
    current_user: CurrentUser = Depends(require_admin_or_manager),
    use_case: ListActiveManagersUseCase = Depends(get_list_active_managers_use_case),
) -> list[AdminUserSummaryDTO]:
    return use_case.execute(actor_id=current_user.id)


@router.get(
    "/active-users",
    response_model=list[AdminUserSummaryDTO],
    summary="Listar usuarios activos (Administrador o Gerente)",
)
def list_active_users(
    q: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_admin_or_manager),
    use_case: ListActiveUsersUseCase = Depends(get_list_active_users_use_case),
) -> list[AdminUserSummaryDTO]:
    return use_case.execute(actor_id=current_user.id, query=q)


@router.post(
    "/admin/users",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario Gerente o Desarrollador (solo Administrador)",
)
def create_user_by_admin(
    cmd: CreateUserByAdminCommand,
    current_user: CurrentUser = Depends(require_admin),
    use_case: CreateUserByAdminUseCase = Depends(get_create_user_by_admin_use_case),
) -> MessageResponse:
    return use_case.execute(actor_id=current_user.id, cmd=cmd)


@router.post(
    "/manager/users/invite",
    response_model=InviteDeveloperResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invitar Desarrollador (solo Gerente)",
)
def invite_developer(
    cmd: InviteDeveloperCommand,
    current_user: CurrentUser = Depends(require_manager),
    use_case: InviteDeveloperByManagerUseCase = Depends(get_invite_developer_use_case),
) -> InviteDeveloperResponse:
    return use_case.execute(actor_id=current_user.id, cmd=cmd)


@router.get(
    "/manager/developers",
    response_model=list[ManagerDeveloperSummaryDTO],
    summary="Desarrolladores solicitados por el gerente",
)
def list_manager_developers(
    current_user: CurrentUser = Depends(require_manager),
    use_case: ListManagerDevelopersUseCase = Depends(get_list_manager_developers_use_case),
) -> list[ManagerDeveloperSummaryDTO]:
    return use_case.execute(actor_id=current_user.id)


@router.post(
    "/manager/developers/{user_id}/deactivate",
    response_model=MessageResponse,
    summary="Desactivar desarrollador del equipo del gerente",
)
def deactivate_manager_developer(
    user_id: str,
    current_user: CurrentUser = Depends(require_manager),
    use_case: DeactivateDeveloperByManagerUseCase = Depends(
        get_deactivate_developer_by_manager_use_case
    ),
) -> MessageResponse:
    return use_case.execute(actor_id=current_user.id, target_user_id=user_id)


@router.post(
    "/manager/developers/{user_id}/reactivate",
    response_model=MessageResponse,
    summary="Reactivar desarrollador del equipo del gerente",
)
def reactivate_manager_developer(
    user_id: str,
    current_user: CurrentUser = Depends(require_manager),
    use_case: ReactivateDeveloperByManagerUseCase = Depends(
        get_reactivate_developer_by_manager_use_case
    ),
) -> MessageResponse:
    return use_case.execute(actor_id=current_user.id, target_user_id=user_id)


@router.post(
    "/admin/users/{user_id}/password-reset",
    response_model=MessageResponse,
    summary="Enviar restablecimiento al correo del usuario (solo Administrador)",
)
def admin_request_password_reset(
    user_id: str,
    current_user: CurrentUser = Depends(require_admin),
    use_case: AdminRequestPasswordResetUseCase = Depends(get_admin_request_password_reset_use_case),
) -> MessageResponse:
    return use_case.execute(actor_id=current_user.id, target_user_id=user_id)
