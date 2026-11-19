"""EP-16 DevOps practices hub routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.devops.application.dtos import (
    DevOpsProfileResponse,
    DevOpsRevisionListResponse,
    UpsertDevOpsProfileRequest,
)
from app.modules.devops.application.use_cases import (
    GetProjectDevOpsProfileUseCase,
    ListProjectDevOpsRevisionsUseCase,
    UpsertProjectDevOpsProfileUseCase,
)
from app.modules.devops.infrastructure.repositories import SqlAlchemyDevOpsProfileRepository
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(prefix="/projects", tags=["devops"])
_clock = SystemClock()
_id_gen = UuidGenerator()


def _get_use_case(db: Session = Depends(get_db_session)) -> GetProjectDevOpsProfileUseCase:
    return GetProjectDevOpsProfileUseCase(
        profiles=SqlAlchemyDevOpsProfileRepository(db),
        projects=SqlAlchemyProjectRepository(db),
        users=SqlAlchemyUserRepository(session=db),
    )


def _upsert_use_case(db: Session = Depends(get_db_session)) -> UpsertProjectDevOpsProfileUseCase:
    return UpsertProjectDevOpsProfileUseCase(
        profiles=SqlAlchemyDevOpsProfileRepository(db),
        projects=SqlAlchemyProjectRepository(db),
        users=SqlAlchemyUserRepository(session=db),
        clock=_clock,
        id_gen=_id_gen,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


def _list_revisions_use_case(
    db: Session = Depends(get_db_session),
) -> ListProjectDevOpsRevisionsUseCase:
    return ListProjectDevOpsRevisionsUseCase(
        profiles=SqlAlchemyDevOpsProfileRepository(db),
        projects=SqlAlchemyProjectRepository(db),
        users=SqlAlchemyUserRepository(session=db),
    )


@router.get(
    "/{project_id}/devops",
    response_model=DevOpsProfileResponse,
    summary="Perfil de prácticas DevOps del proyecto",
)
def get_devops_profile(
    project_id: str,
    response: Response,
    actor: CurrentUser = Depends(get_current_user),
    use_case: GetProjectDevOpsProfileUseCase = Depends(_get_use_case),
) -> DevOpsProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return use_case.execute(project_id, actor)


@router.put(
    "/{project_id}/devops",
    response_model=DevOpsProfileResponse,
    summary="Crear o actualizar prácticas DevOps (admin/gerente)",
)
def upsert_devops_profile(
    project_id: str,
    payload: UpsertDevOpsProfileRequest,
    actor: CurrentUser = Depends(get_current_user),
    use_case: UpsertProjectDevOpsProfileUseCase = Depends(_upsert_use_case),
) -> DevOpsProfileResponse:
    return use_case.execute(project_id, payload, actor)


@router.get(
    "/{project_id}/devops/revisions",
    response_model=DevOpsRevisionListResponse,
    summary="Historial de cambios en prácticas DevOps",
)
def list_devops_revisions(
    project_id: str,
    response: Response,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: CurrentUser = Depends(get_current_user),
    use_case: ListProjectDevOpsRevisionsUseCase = Depends(_list_revisions_use_case),
) -> DevOpsRevisionListResponse:
    response.headers["Cache-Control"] = "no-store"
    return use_case.execute(project_id, actor, limit=limit, offset=offset)
