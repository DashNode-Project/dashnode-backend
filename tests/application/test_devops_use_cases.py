"""DevOps use-case behaviour with fakes."""

from datetime import datetime, timedelta
from typing import cast

import pytest

from app.modules.auth.domain.entities import User, UserRole
from app.modules.auth.domain.ports import UserRepository
from app.modules.devops.application.use_cases import (
    GetLatestPipelineUseCase,
    TriggerPipelineUseCase,
)
from app.modules.devops.domain.entities import (
    DevopsOutcome,
    DevopsStage,
    DevopsTrigger,
    PipelineRun,
    PipelineStagePlan,
    SimConfig,
)
from app.modules.devops.domain.ports import DevopsPipelineRepository
from app.modules.projects.domain.ports import ProjectRepository
from app.shared.application.identity import CurrentUser
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError
from tests.fakes import T0, FakeClock, FakeIdGenerator, FakeUnitOfWork


class _FakeProjects:
    def __init__(self, *, exists: bool, access: bool) -> None:
        self._exists = exists
        self._access = access

    def get_by_id(self, project_id: str) -> object | None:
        return object() if self._exists else None

    def user_can_access(self, project_id: str, user_id: str, role: str) -> bool:
        return self._access


class _FakePipeline:
    last_saved: PipelineRun

    def load_sim_config(self) -> SimConfig:
        return SimConfig()

    def cooldown_seconds(self) -> int:
        return 0

    def latest_run_created_at(self, project_id: str) -> datetime | None:
        return None

    def save_run(self, run: PipelineRun, *, stage_row_ids: list[str]) -> None:
        self.last_saved = run

    def get_latest(self, project_id: str) -> PipelineRun | None:
        start = T0
        end = start + timedelta(seconds=10)
        return PipelineRun(
            id="run-1",
            project_id=project_id,
            trigger=DevopsTrigger.MANUAL,
            triggered_by="user-1",
            is_simulated=True,
            created_at=start,
            stages=[
                PipelineStagePlan(
                    stage=DevopsStage.LINT,
                    position=1,
                    outcome=DevopsOutcome.SUCCESS,
                    planned_start=start,
                    planned_end=end,
                )
            ],
        )


class _FakeUsers:
    def get_by_id(self, user_id: str) -> User | None:
        return User(
            id=user_id,
            email="ana@b.io",
            hashed_password="hash",
            name="Ana",
            role=UserRole.DEVELOPER,
            is_active=True,
            created_at=T0,
            updated_at=T0,
        )


def _as_projects(*, exists: bool, access: bool) -> ProjectRepository:
    return cast(ProjectRepository, _FakeProjects(exists=exists, access=access))


def _as_users(repo: _FakeUsers) -> UserRepository:
    return cast(UserRepository, repo)


def _as_pipeline(repo: _FakePipeline) -> DevopsPipelineRepository:
    return cast(DevopsPipelineRepository, repo)


def test_trigger_pipeline_denies_non_member() -> None:
    use_case = TriggerPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=True, access=False),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("run-denied"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="mgr-1",
        email="mgr@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AccessDeniedError):
        use_case.execute("proj", actor)


def test_trigger_pipeline_not_found_project() -> None:
    use_case = TriggerPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=False, access=False),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("run-nf"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="mgr-1",
        email="mgr@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AppError) as err:
        use_case.execute("missing", actor)
    assert err.value.code == "NOT_FOUND"


def test_trigger_pipeline_denies_developer() -> None:
    use_case = TriggerPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=True, access=True),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("run-x"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="dev-1",
        email="dev@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AccessDeniedError):
        use_case.execute("proj", actor)


def test_trigger_pipeline_raises_when_cooldown_active() -> None:
    class _CooldownPipeline(_FakePipeline):
        def cooldown_seconds(self) -> int:
            return 300

        def latest_run_created_at(self, project_id: str) -> datetime | None:
            return T0

    use_case = TriggerPipelineUseCase(
        pipeline=_as_pipeline(_CooldownPipeline()),
        projects=_as_projects(exists=True, access=True),
        clock=FakeClock(T0 + timedelta(seconds=30)),
        id_gen=FakeIdGenerator("run-cd"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="mgr-1",
        email="mgr@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AppError) as err:
        use_case.execute("proj", actor)
    assert err.value.code == "COOLDOWN_ACTIVE"


def test_trigger_pipeline_as_manager() -> None:
    pipeline = _FakePipeline()
    use_case = TriggerPipelineUseCase(
        pipeline=_as_pipeline(pipeline),
        projects=_as_projects(exists=True, access=True),
        clock=FakeClock(T0),
        id_gen=FakeIdGenerator("run-new"),
        uow=FakeUnitOfWork(),
    )
    actor = CurrentUser(
        id="mgr-1",
        email="mgr@b.io",
        role="manager",
        name="Mgr",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    assert result.run_id == "run-new"
    assert pipeline.last_saved.project_id == "proj"


def test_get_latest_empty_pipeline() -> None:
    class _EmptyPipeline(_FakePipeline):
        def get_latest(self, project_id: str) -> PipelineRun | None:
            return None

    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_EmptyPipeline()),
        projects=_as_projects(exists=True, access=True),
        users=_as_users(_FakeUsers()),
        clock=FakeClock(T0),
    )
    actor = CurrentUser(
        id="u1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    assert result.run_id is None
    assert result.stages == []


def test_get_latest_denies_non_member() -> None:
    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=True, access=False),
        users=_as_users(_FakeUsers()),
        clock=FakeClock(T0),
    )
    actor = CurrentUser(
        id="u1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AccessDeniedError):
        use_case.execute("proj", actor)


def test_get_latest_seed_run_labels_trigger() -> None:
    start = T0
    end = start + timedelta(seconds=10)
    seed_run = PipelineRun(
        id="seed",
        project_id="proj",
        trigger=DevopsTrigger.SEED,
        triggered_by=None,
        is_simulated=True,
        created_at=start,
        stages=[
            PipelineStagePlan(
                stage=DevopsStage.LINT,
                position=1,
                outcome=DevopsOutcome.SUCCESS,
                planned_start=start,
                planned_end=end,
            )
        ],
    )

    class _SeedPipeline(_FakePipeline):
        def get_latest(self, project_id: str) -> PipelineRun | None:
            return seed_run

    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_SeedPipeline()),
        projects=_as_projects(exists=True, access=True),
        users=_as_users(_FakeUsers()),
        clock=FakeClock(end + timedelta(seconds=1)),
    )
    actor = CurrentUser(
        id="u1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    assert result.triggered_by is not None
    assert result.triggered_by.name == "Semilla inicial"


def test_get_latest_marks_skip_reason_after_failure() -> None:
    start = T0
    mid = start + timedelta(seconds=5)
    run = PipelineRun(
        id="fail-run",
        project_id="proj",
        trigger=DevopsTrigger.MANUAL,
        triggered_by="user-1",
        is_simulated=True,
        created_at=start,
        stages=[
            PipelineStagePlan(
                stage=DevopsStage.LINT,
                position=1,
                outcome=DevopsOutcome.FAILED,
                planned_start=start,
                planned_end=mid,
            ),
            PipelineStagePlan(
                stage=DevopsStage.TEST,
                position=2,
                outcome=DevopsOutcome.SKIPPED,
                planned_start=mid,
                planned_end=mid,
            ),
        ],
    )

    class _FailedPipeline(_FakePipeline):
        def get_latest(self, project_id: str) -> PipelineRun | None:
            return run

    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_FailedPipeline()),
        projects=_as_projects(exists=True, access=True),
        users=_as_users(_FakeUsers()),
        clock=FakeClock(mid + timedelta(seconds=1)),
    )
    actor = CurrentUser(
        id="user-1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    test_stage = next(stage for stage in result.stages if stage.stage == "TEST")
    assert test_stage.skip_reason is not None
    assert "LINT" in test_stage.skip_reason


def test_get_latest_omits_triggered_by_when_user_missing() -> None:
    class _MissingUserRepo(_FakeUsers):
        def get_by_id(self, user_id: str) -> User | None:
            return None

    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=True, access=True),
        users=_as_users(_MissingUserRepo()),
        clock=FakeClock(T0 + timedelta(seconds=15)),
    )
    actor = CurrentUser(
        id="user-1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    assert result.triggered_by is None


def test_get_latest_returns_computed_stages() -> None:
    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=True, access=True),
        users=_as_users(_FakeUsers()),
        clock=FakeClock(T0 + timedelta(seconds=15)),
    )
    actor = CurrentUser(
        id="user-1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    result = use_case.execute("proj", actor)
    assert result.run_id == "run-1"
    assert len(result.stages) == 1
    assert result.triggered_by is not None


def test_get_latest_not_found() -> None:
    use_case = GetLatestPipelineUseCase(
        pipeline=_as_pipeline(_FakePipeline()),
        projects=_as_projects(exists=False, access=False),
        users=_as_users(_FakeUsers()),
        clock=FakeClock(T0),
    )
    actor = CurrentUser(
        id="u1",
        email="a@b.io",
        role="developer",
        name="Dev",
        is_active=True,
        created_at=T0,
    )
    with pytest.raises(AppError) as err:
        use_case.execute("missing", actor)
    assert err.value.code == "NOT_FOUND"
