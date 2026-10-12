"""
HTTP routes that compose auth use cases with cross-module adapters (BR-4).

User update needs project-ownership checks; wiring lives here so `auth.api.routes`
does not transitively import the projects module.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.modules.auth.application.dtos import UpdateUserByAdminCommand, UpdateUserByAdminResponse
from app.modules.auth.application.user_administration_use_cases import UpdateUserByAdminUseCase
from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
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
