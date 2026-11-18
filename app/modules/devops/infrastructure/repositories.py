"""DevOps pipeline persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai.infrastructure.models import SystemConfigModel
from app.modules.devops.domain.entities import (
    DevopsOutcome,
    DevopsStage,
    DevopsTrigger,
    PipelineRun,
    PipelineStagePlan,
    SimConfig,
)
from app.modules.devops.infrastructure.models import (
    DevopsPipelineRunModel,
    DevopsPipelineStageRunModel,
)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class SqlAlchemyDevopsPipelineRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load_sim_config(self) -> SimConfig:
        keys = {
            "devops_sim_success_lint": "success_lint",
            "devops_sim_success_test": "success_test",
            "devops_sim_success_build": "success_build",
            "devops_sim_success_deploy": "success_deploy",
            "devops_sim_duration_lint_s": "duration_lint_s",
            "devops_sim_duration_test_s": "duration_test_s",
            "devops_sim_duration_build_s": "duration_build_s",
            "devops_sim_duration_deploy_s": "duration_deploy_s",
        }
        defaults = SimConfig()
        values: dict[str, float | int] = {
            "success_lint": defaults.success_lint,
            "success_test": defaults.success_test,
            "success_build": defaults.success_build,
            "success_deploy": defaults.success_deploy,
            "duration_lint_s": defaults.duration_lint_s,
            "duration_test_s": defaults.duration_test_s,
            "duration_build_s": defaults.duration_build_s,
            "duration_deploy_s": defaults.duration_deploy_s,
        }
        rows = self._session.scalars(
            select(SystemConfigModel).where(SystemConfigModel.key.in_(keys.keys()))
        ).all()
        by_key = {row.key: row.value for row in rows}
        for key, attr in keys.items():
            raw = by_key.get(key)
            if raw is None:
                continue
            if attr.startswith("duration"):
                values[attr] = int(float(raw))
            else:
                values[attr] = float(raw)
        return SimConfig(
            success_lint=float(values["success_lint"]),
            success_test=float(values["success_test"]),
            success_build=float(values["success_build"]),
            success_deploy=float(values["success_deploy"]),
            duration_lint_s=int(values["duration_lint_s"]),
            duration_test_s=int(values["duration_test_s"]),
            duration_build_s=int(values["duration_build_s"]),
            duration_deploy_s=int(values["duration_deploy_s"]),
        )

    def cooldown_seconds(self) -> int:
        row = self._session.get(SystemConfigModel, "devops_manual_run_cooldown_s")
        if row is None:
            return 300
        return int(float(row.value))

    def latest_run_created_at(self, project_id: str) -> DevopsPipelineRunModel | None:
        row = self._session.scalars(
            select(DevopsPipelineRunModel)
            .where(DevopsPipelineRunModel.project_id == project_id)
            .order_by(
                DevopsPipelineRunModel.created_at.desc(),
                DevopsPipelineRunModel.id.desc(),
            )
            .limit(1)
        ).first()
        if row is not None:
            row.created_at = _aware(row.created_at)
        return row

    def save_run(self, run: PipelineRun, *, stage_row_ids: list[str]) -> None:
        self._session.add(
            DevopsPipelineRunModel(
                id=run.id,
                project_id=run.project_id,
                trigger=run.trigger.value,
                triggered_by=run.triggered_by,
                is_simulated=run.is_simulated,
                created_at=run.created_at,
            )
        )
        for plan, stage_id in zip(run.stages, stage_row_ids, strict=True):
            self._session.add(
                DevopsPipelineStageRunModel(
                    id=stage_id,
                    run_id=run.id,
                    stage=plan.stage.value,
                    position=plan.position,
                    outcome=plan.outcome.value,
                    planned_start=plan.planned_start,
                    planned_end=plan.planned_end,
                )
            )

    def get_latest(self, project_id: str) -> PipelineRun | None:
        row = self.latest_run_created_at(project_id)
        if row is None:
            return None
        stage_rows = self._session.scalars(
            select(DevopsPipelineStageRunModel)
            .where(DevopsPipelineStageRunModel.run_id == row.id)
            .order_by(DevopsPipelineStageRunModel.position.asc())
        ).all()
        stages = [
            PipelineStagePlan(
                stage=DevopsStage(s.stage),
                position=s.position,
                outcome=DevopsOutcome(s.outcome),
                planned_start=_aware(s.planned_start),
                planned_end=_aware(s.planned_end),
            )
            for s in stage_rows
        ]
        return PipelineRun(
            id=row.id,
            project_id=row.project_id,
            trigger=DevopsTrigger(row.trigger),
            triggered_by=row.triggered_by,
            is_simulated=row.is_simulated,
            created_at=_aware(row.created_at),
            stages=stages,
        )
