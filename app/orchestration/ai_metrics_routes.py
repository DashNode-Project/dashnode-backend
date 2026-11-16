"""HTTP routes for EP-13 AI metrics and interaction registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.ai_metrics.application.ai_metrics_service import AiMetricsService
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.database import get_db_session

router = APIRouter(prefix="/ai", tags=["ai-metrics"])


class RatingBody(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


def _service(db: Session = Depends(get_db_session)) -> AiMetricsService:
    return AiMetricsService(db)


@router.get("/metrics/summary")
def metrics_summary(
    actor: CurrentUser = Depends(get_current_user),
    service: AiMetricsService = Depends(_service),
    period: str | None = Query(default="30d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    result = service.get_summary(
        actor, period=period, from_iso=from_, to_iso=to, project_id=project_id
    )
    db.commit()
    return result


@router.get("/metrics/by-user")
def metrics_by_user(
    actor: CurrentUser = Depends(get_current_user),
    service: AiMetricsService = Depends(_service),
    period: str | None = Query(default="30d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    result = service.get_by_user(
        actor, period=period, from_iso=from_, to_iso=to, project_id=project_id
    )
    db.commit()
    return result


@router.get("/metrics/interactions")
def metrics_interactions(
    actor: CurrentUser = Depends(get_current_user),
    service: AiMetricsService = Depends(_service),
    period: str | None = Query(default="30d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    result = service.list_interactions(
        actor,
        period=period,
        from_iso=from_,
        to_iso=to,
        project_id=project_id,
        source=source,
        limit=limit,
        offset=offset,
    )
    db.commit()
    return result


@router.get("/interactions/{interaction_id}")
def interaction_detail(
    interaction_id: str,
    actor: CurrentUser = Depends(get_current_user),
    service: AiMetricsService = Depends(_service),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    result = service.get_interaction_detail(actor, interaction_id)
    db.commit()
    return result


@router.put("/interactions/{interaction_id}/rating")
def rate_interaction(
    interaction_id: str,
    body: RatingBody,
    actor: CurrentUser = Depends(get_current_user),
    service: AiMetricsService = Depends(_service),
    db: Session = Depends(get_db_session),
) -> dict[str, str]:
    result = service.upsert_rating(
        actor, interaction_id, score=body.score, comment=body.comment
    )
    db.commit()
    return result