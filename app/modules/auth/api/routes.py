"""
FastAPI router for Authentication module.
Complies strictly with BR-1 (no direct DB/infrastructure imports).
@sad 4.1.1, AD-08
@origin [SAD-Propuesto]
"""

from fastapi import APIRouter, Depends, Response, status

from app.config import settings
from app.modules.auth.application.dtos import (
    LoginCommand,
    LogoutResponse,
    RegisterManagerCommand,
    RegisterManagerResponse,
    SessionInfo,
)
from app.modules.auth.application.session_use_cases import LoginUseCase, LogoutUseCase
from app.modules.auth.application.use_cases import RegisterManagerUseCase
from app.orchestration.auth_container import (
    get_login_use_case,
    get_logout_use_case,
    get_register_manager_use_case,
)
from app.orchestration.security import get_current_session, get_session_token
from app.shared.application.identity import CurrentSession

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
    "/me",
    response_model=CurrentSession,
    summary="Perfil y vigencia de la sesion actual",
)
def get_me(session: CurrentSession = Depends(get_current_session)) -> CurrentSession:
    return session
