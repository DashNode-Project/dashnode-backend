"""Simulated CI pipeline (DVO-02 .. DVO-04)."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

from app.modules.devops.domain.entities import (
    DevopsOutcome,
    DevopsStage,
    DevopsTrigger,
    PipelineRun,
    PipelineStagePlan,
    RunDisplayStatus,
    SimConfig,
    StageDisplayStatus,
)

STAGE_ORDER: tuple[DevopsStage, ...] = (
    DevopsStage.LINT,
    DevopsStage.TEST,
    DevopsStage.BUILD,
    DevopsStage.DEPLOY,
)


def _success_rate(stage: DevopsStage, cfg: SimConfig) -> float:
    mapping = {
        DevopsStage.LINT: cfg.success_lint,
        DevopsStage.TEST: cfg.success_test,
        DevopsStage.BUILD: cfg.success_build,
        DevopsStage.DEPLOY: cfg.success_deploy,
    }
    return mapping[stage]


def _duration(stage: DevopsStage, cfg: SimConfig) -> int:
    mapping = {
        DevopsStage.LINT: cfg.duration_lint_s,
        DevopsStage.TEST: cfg.duration_test_s,
        DevopsStage.BUILD: cfg.duration_build_s,
        DevopsStage.DEPLOY: cfg.duration_deploy_s,
    }
    return mapping[stage]


def _rng_for_run(run_id: str) -> random.Random:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    seed = int(digest[:16], 16)
    return random.Random(seed)  # noqa: S311 — deterministic demo simulation, not security


def plan_stages(
    *,
    run_id: str,
    start_at: datetime,
    cfg: SimConfig,
) -> list[PipelineStagePlan]:
    rng = _rng_for_run(run_id)
    cursor = start_at
    plans: list[PipelineStagePlan] = []
    failed = False
    for position, stage in enumerate(STAGE_ORDER, start=1):
        if failed:
            plans.append(
                PipelineStagePlan(
                    stage=stage,
                    position=position,
                    outcome=DevopsOutcome.SKIPPED,
                    planned_start=cursor,
                    planned_end=cursor,
                )
            )
            continue
        duration = _duration(stage, cfg)
        end = cursor + timedelta(seconds=duration)
        success = rng.random() < _success_rate(stage, cfg)
        outcome = DevopsOutcome.SUCCESS if success else DevopsOutcome.FAILED
        plans.append(
            PipelineStagePlan(
                stage=stage,
                position=position,
                outcome=outcome,
                planned_start=cursor,
                planned_end=end,
            )
        )
        cursor = end
        if not success:
            failed = True
    return plans


def derive_stage_status(plan: PipelineStagePlan, now: datetime) -> StageDisplayStatus:
    if plan.outcome == DevopsOutcome.SKIPPED:
        return StageDisplayStatus.OMITIDA
    if now < plan.planned_start:
        return StageDisplayStatus.PENDIENTE
    if plan.planned_start <= now < plan.planned_end:
        return StageDisplayStatus.EN_EJECUCION
    if plan.outcome == DevopsOutcome.SUCCESS:
        return StageDisplayStatus.EXITOSA
    return StageDisplayStatus.FALLIDA


def derive_run_status(plans: list[PipelineStagePlan], now: datetime) -> RunDisplayStatus:
    statuses = [derive_stage_status(p, now) for p in plans]
    if any(s == StageDisplayStatus.FALLIDA for s in statuses):
        return RunDisplayStatus.FALLIDA
    if any(s in (StageDisplayStatus.EN_EJECUCION, StageDisplayStatus.PENDIENTE) for s in statuses):
        return RunDisplayStatus.EN_EJECUCION
    return RunDisplayStatus.EXITOSA


def build_run(
    *,
    run_id: str,
    project_id: str,
    trigger: DevopsTrigger,
    triggered_by: str | None,
    created_at: datetime,
    cfg: SimConfig,
) -> PipelineRun:
    stages = plan_stages(run_id=run_id, start_at=created_at, cfg=cfg)
    return PipelineRun(
        id=run_id,
        project_id=project_id,
        trigger=trigger,
        triggered_by=triggered_by,
        is_simulated=True,
        created_at=created_at,
        stages=stages,
    )
