"""
FastAPI router for Authentication module.
Complies strictly with BR-1 (no direct DB/infrastructure imports).
@sad 4.1.1, AD-08
@origin [SAD-Propuesto]
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.application.dtos import (
    LoginCommand,
    RegisterManagerCommand,
    RegisterManagerResponse,
    TokenResponse,
)
from app.modules.auth.application.use_cases import (
    LoginUseCase,
    RegisterManagerUseCase,
)
from app.orchestration.auth_container import (
    get_login_use_case,
    get_register_manager_use_case,
)
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser

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
    response_model=TokenResponse,
    summary="Iniciar sesión y obtener token JWT",
)
def login(
    cmd: LoginCommand,
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> TokenResponse:
    try:
        return use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e


@router.get(
    "/me",
    response_model=CurrentUser,
    summary="Obtener perfil del usuario autenticado",
)
def get_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    return current_user
