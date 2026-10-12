"""
HTTP routes that compose auth use cases with cross-module adapters (BR-4).

User update needs project-ownership checks; wiring lives here so `auth.api.routes`
does not transitively import the projects module.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.modules.auth.application.dtos import MessageResponse, UpdateUserByAdminCommand, UpdateUserByAdminResponse
from app.modules.auth.application.user_administration_use_cases import UpdateUserByAdminUseCase
from app.modules.auth.application.user_lifecycle_use_cases import (
    DeactivateUserByAdminUseCase,
    GetPendingAssignmentsUseCase,
    ReactivateUserByAdminUseCase,
)
from app.modules.auth.infrastructure.repositories import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from app.orchestration.pending_assignments_query import SqlAlchemyPendingAssignmentsQuery
from app.orchestration.project_ownership_query import SqlAlchemyProjectOwnershipQuery
from app.orchestration.security import require_admin
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])

_clock = SystemClock()


def get_update_user_by_admin_use_case(
    db: Session = Depends(get_db_session),
) -> UpdateUserByAdminUseCase:
    return UpdateUserByAdminUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        project_ownership=SqlAlchemyProjectOwnershipQuery(session=db),
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


@router.patch(
    "/admin/users/{user_id}",
    response_model=UpdateUserByAdminResponse,
    summary="Editar usuario (solo Administrador)",
)
def update_user_by_admin(
    user_id: str,
    cmd: UpdateUserByAdminCommand,
    current_user: CurrentUser = Depends(require_admin),
    use_case: UpdateUserByAdminUseCase = Depends(get_update_user_by_admin_use_case),
) -> UpdateUserByAdminResponse:
    return use_case.execute(actor_id=current_user.id, user_id=user_id, cmd=cmd)


def _lifecycle_deps(db: Session):
    return {
        "users": SqlAlchemyUserRepository(session=db),
        "sessions": SqlAlchemySessionRepository(session=db),
        "projects": SqlAlchemyProjectOwnershipQuery(session=db),
        "pending": SqlAlchemyPendingAssignmentsQuery(session=db),
        "uow": SqlAlchemyUnitOfWork(session=db),
        "clock": _clock,
    }


@router.post(
    "/admin/users/{user_id}/deactivate",
    response_model=MessageResponse,
    summary="Desactivar usuario (solo Administrador)",
)
def deactivate_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    d = _lifecycle_deps(db)
    use_case = DeactivateUserByAdminUseCase(
        user_repo=d["users"],
        session_repo=d["sessions"],
        project_ownership=d["projects"],
        clock=d["clock"],
        uow=d["uow"],
    )
    return use_case.execute(actor_id=current_user.id, target_user_id=user_id)


@router.post(
    "/admin/users/{user_id}/reactivate",
    response_model=MessageResponse,
    summary="Reactivar usuario (solo Administrador)",
)
def reactivate_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> MessageResponse:
    d = _lifecycle_deps(db)
    use_case = ReactivateUserByAdminUseCase(
        user_repo=d["users"],
        clock=d["clock"],
        uow=d["uow"],
    )
    return use_case.execute(actor_id=current_user.id, target_user_id=user_id)


@router.get(
    "/admin/users/{user_id}/pending-assignments",
    summary="Conteo de tareas pendientes (HU_DN_01_19)",
)
def pending_assignments(
    user_id: str,
    current_user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> dict[str, int]:
    d = _lifecycle_deps(db)
    use_case = GetPendingAssignmentsUseCase(user_repo=d["users"], pending=d["pending"])
    return use_case.execute(actor_id=current_user.id, target_user_id=user_id)
