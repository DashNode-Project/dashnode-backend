"""EP-16 DevOps simulated pipeline routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.devops.application.dtos import LatestPipelineResponse, TriggerPipelineResponse
from app.modules.devops.application.use_cases import (
    GetLatestPipelineUseCase,
    TriggerPipelineUseCase,
)
from app.modules.devops.infrastructure.repositories import SqlAlchemyDevopsPipelineRepository
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(prefix="/projects", tags=["devops"])
_clock = SystemClock()
_id_gen = UuidGenerator()


def _latest_use_case(db: Session = Depends(get_db_session)) -> GetLatestPipelineUseCase:
    return GetLatestPipelineUseCase(
        pipeline=SqlAlchemyDevopsPipelineRepository(db),
        projects=SqlAlchemyProjectRepository(db),
        users=SqlAlchemyUserRepository(session=db),
        clock=_clock,
    )


def _trigger_use_case(db: Session = Depends(get_db_session)) -> TriggerPipelineUseCase:
    return TriggerPipelineUseCase(
        pipeline=SqlAlchemyDevopsPipelineRepository(db),
        projects=SqlAlchemyProjectRepository(db),
        clock=_clock,
        id_gen=_id_gen,
        uow=SqlAlchemyUnitOfWork(session=db),
    )


@router.get(
    "/{project_id}/devops/pipeline/latest",
    response_model=LatestPipelineResponse,
    summary="Última ejecución simulada del pipeline",
)
def get_latest_pipeline(
    project_id: str,
    response: Response,
    actor: CurrentUser = Depends(get_current_user),
    use_case: GetLatestPipelineUseCase = Depends(_latest_use_case),
) -> LatestPipelineResponse:
    response.headers["Cache-Control"] = "no-store"
    return use_case.execute(project_id, actor)


@router.post(
    "/{project_id}/devops/pipeline/runs",
    response_model=TriggerPipelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Disparar una ejecución simulada del pipeline",
)
def trigger_pipeline(
    project_id: str,
    actor: CurrentUser = Depends(get_current_user),
    use_case: TriggerPipelineUseCase = Depends(_trigger_use_case),
) -> TriggerPipelineResponse:
    return use_case.execute(project_id, actor)
