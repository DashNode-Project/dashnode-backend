"""Unit tests for the simulated DevOps pipeline (EP-16)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.devops.application.pipeline_simulator import (
    build_run,
    derive_run_status,
    derive_stage_status,
    plan_stages,
)
from app.modules.devops.domain.entities import (
    DevopsOutcome,
    DevopsStage,
    DevopsTrigger,
    PipelineStagePlan,
    RunDisplayStatus,
    SimConfig,
    StageDisplayStatus,
)


def test_plan_stages_cascade_skip_after_failure() -> None:
    cfg = SimConfig(success_lint=0.0, success_test=1.0, success_build=1.0, success_deploy=1.0)
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    plans = plan_stages(run_id="run-fixed", start_at=start, cfg=cfg)
    assert plans[0].outcome == DevopsOutcome.FAILED
    assert all(p.outcome == DevopsOutcome.SKIPPED for p in plans[1:])


def test_same_seed_reproduces_outcomes() -> None:
    cfg = SimConfig()
    start = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    a = plan_stages(run_id="seed-run-1", start_at=start, cfg=cfg)
    b = plan_stages(run_id="seed-run-1", start_at=start, cfg=cfg)
    assert [(p.stage, p.outcome) for p in a] == [(p.stage, p.outcome) for p in b]


@pytest.mark.parametrize(
    ("offset_seconds", "expected"),
    [
        (-1, StageDisplayStatus.PENDIENTE),
        (5, StageDisplayStatus.EN_EJECUCION),
        (60, StageDisplayStatus.FALLIDA),
    ],
)
def test_derive_stage_status_transitions(offset_seconds: int, expected: StageDisplayStatus) -> None:
    start = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    end = start + timedelta(seconds=10)
    plan = PipelineStagePlan(
        stage=DevopsStage.LINT,
        position=1,
        outcome=DevopsOutcome.FAILED,
        planned_start=start,
        planned_end=end,
    )
    now = start + timedelta(seconds=offset_seconds)
    assert derive_stage_status(plan, now) == expected


def test_derive_stage_status_success_after_planned_end() -> None:
    start = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    end = start + timedelta(seconds=10)
    plan = PipelineStagePlan(
        stage=DevopsStage.BUILD,
        position=3,
        outcome=DevopsOutcome.SUCCESS,
        planned_start=start,
        planned_end=end,
    )
    assert derive_stage_status(plan, end) == StageDisplayStatus.EXITOSA


def test_derive_stage_status_skipped_is_omitida() -> None:
    start = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    plan = PipelineStagePlan(
        stage=DevopsStage.DEPLOY,
        position=4,
        outcome=DevopsOutcome.SKIPPED,
        planned_start=start,
        planned_end=start,
    )
    assert derive_stage_status(plan, start) == StageDisplayStatus.OMITIDA


def test_derive_stage_status_with_controlled_clock() -> None:
    cfg = SimConfig(duration_lint_s=10)
    start = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    plans = plan_stages(run_id="clock-run", start_at=start, cfg=cfg)
    lint = plans[0]
    assert derive_stage_status(lint, start - timedelta(seconds=1)) == StageDisplayStatus.PENDIENTE
    mid = start + timedelta(seconds=5)
    assert derive_stage_status(lint, mid) == StageDisplayStatus.EN_EJECUCION
    after = lint.planned_end + timedelta(seconds=1)
    assert derive_stage_status(lint, after) in (
        StageDisplayStatus.EXITOSA,
        StageDisplayStatus.FALLIDA,
    )


def test_derive_run_status_failed_when_any_stage_fails() -> None:
    cfg = SimConfig(success_lint=0.0, success_test=1.0, success_build=1.0, success_deploy=1.0)
    start = datetime(2026, 5, 2, 8, 0, tzinfo=UTC)
    plans = plan_stages(run_id="fail-global", start_at=start, cfg=cfg)
    end = plans[-1].planned_end + timedelta(seconds=5)
    assert derive_run_status(plans, end) == RunDisplayStatus.FALLIDA


def test_build_run_global_status_running_then_done() -> None:
    cfg = SimConfig(
        success_lint=1.0,
        success_test=1.0,
        success_build=1.0,
        success_deploy=1.0,
        duration_lint_s=5,
        duration_test_s=5,
        duration_build_s=5,
        duration_deploy_s=5,
    )
    start = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
    run = build_run(
        run_id="complete-run",
        project_id="proj-1",
        trigger=DevopsTrigger.MANUAL,
        triggered_by="user-1",
        created_at=start,
        cfg=cfg,
    )
    assert derive_run_status(run.stages, start) == RunDisplayStatus.EN_EJECUCION
    end = run.stages[-1].planned_end + timedelta(seconds=1)
    assert derive_run_status(run.stages, end) == RunDisplayStatus.EXITOSA
