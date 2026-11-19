"""DevOps practices persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.devops.domain.entities import (
    DevOpsRevision,
    EnvironmentSpec,
    PipelineStageSpec,
    ProjectDevOpsProfile,
)
from app.modules.devops.infrastructure.models import (
    ProjectDevOpsProfileModel,
    ProjectDevOpsRevisionModel,
)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_entity(row: ProjectDevOpsProfileModel) -> ProjectDevOpsProfile:
    return ProjectDevOpsProfile(
        id=row.id,
        project_id=row.project_id,
        repository_url=row.repository_url,
        ci_cd_provider=row.ci_cd_provider,
        branching_strategy=row.branching_strategy,
        branching_rules_md=row.branching_rules_md,
        pipeline_stages=[PipelineStageSpec.from_dict(item) for item in row.pipeline_stages or []],
        environments=[EnvironmentSpec.from_dict(item) for item in row.environments or []],
        quality_gates_md=row.quality_gates_md,
        deployment_runbook_md=row.deployment_runbook_md,
        rollback_observability_md=row.rollback_observability_md,
        updated_by=row.updated_by,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


class SqlAlchemyDevOpsProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_project_id(self, project_id: str) -> ProjectDevOpsProfile | None:
        row = self._session.scalars(
            select(ProjectDevOpsProfileModel).where(
                ProjectDevOpsProfileModel.project_id == project_id
            )
        ).first()
        if row is None:
            return None
        return _to_entity(row)

    def save(self, profile: ProjectDevOpsProfile) -> None:
        assert profile.id is not None
        row = self._session.get(ProjectDevOpsProfileModel, profile.id)
        if row is None:
            row = ProjectDevOpsProfileModel(
                id=profile.id,
                project_id=profile.project_id,
                created_at=profile.created_at or profile.updated_at,
            )
            self._session.add(row)
        row.repository_url = profile.repository_url
        row.ci_cd_provider = profile.ci_cd_provider
        row.branching_strategy = profile.branching_strategy
        row.branching_rules_md = profile.branching_rules_md
        row.pipeline_stages = [stage.to_dict() for stage in profile.pipeline_stages]
        row.environments = [env.to_dict() for env in profile.environments]
        row.quality_gates_md = profile.quality_gates_md
        row.deployment_runbook_md = profile.deployment_runbook_md
        row.rollback_observability_md = profile.rollback_observability_md
        row.updated_by = profile.updated_by
        row.updated_at = profile.updated_at or row.updated_at

    def add_revision(self, revision: DevOpsRevision) -> None:
        self._session.add(
            ProjectDevOpsRevisionModel(
                id=revision.id,
                profile_id=revision.profile_id,
                project_id=revision.project_id,
                changed_by=revision.changed_by,
                change_summary=revision.change_summary,
                snapshot=revision.snapshot,
                created_at=revision.created_at,
            )
        )

    def list_revisions(
        self,
        project_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[DevOpsRevision]:
        rows = self._session.scalars(
            select(ProjectDevOpsRevisionModel)
            .where(ProjectDevOpsRevisionModel.project_id == project_id)
            .order_by(
                ProjectDevOpsRevisionModel.created_at.desc(),
                ProjectDevOpsRevisionModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return [
            DevOpsRevision(
                id=row.id,
                profile_id=row.profile_id,
                project_id=row.project_id,
                changed_by=row.changed_by,
                change_summary=row.change_summary,
                snapshot=row.snapshot,
                created_at=_aware(row.created_at),
            )
            for row in rows
        ]
