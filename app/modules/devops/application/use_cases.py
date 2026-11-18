"""DevOps pipeline use cases (EP-16)."""

from __future__ import annotations

from app.modules.auth.domain.ports import UserRepository
from app.modules.devops.application.dtos import (
    LatestPipelineResponse,
    PipelineStageDTO,
    TriggeredByDTO,
    TriggerPipelineResponse,
)
from app.modules.devops.application.pipeline_simulator import (
    build_run,
    derive_run_status,
    derive_stage_status,
)
from app.modules.devops.domain.entities import DevopsTrigger, StageDisplayStatus
from app.modules.devops.domain.messages import COOLDOWN_ACTIVE, NOT_FOUND_PROJECT
from app.modules.devops.domain.ports import DevopsPipelineRepository
from app.modules.projects.domain.ports import ProjectRepository
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


class GetLatestPipelineUseCase:
    def __init__(
        self,
        *,
        pipeline: DevopsPipelineRepository,
        projects: ProjectRepository,
        users: UserRepository,
        clock: Clock,
    ) -> None:
        self._pipeline = pipeline
        self._projects = projects
        self._users = users
        self._clock = clock

    def execute(self, project_id: str, actor: CurrentUser) -> LatestPipelineResponse:
        if self._projects.get_by_id(project_id) is None:
            raise AppError("NOT_FOUND", NOT_FOUND_PROJECT, ErrorKind.NOT_FOUND)
        if not self._projects.user_can_access(project_id, actor.id, actor.role):
            raise AccessDeniedError()
        now = self._clock.now()
        run = self._pipeline.get_latest(project_id)
        if run is None:
            return LatestPipelineResponse(
                run_id=None,
                computed_at=now,
                stages=[],
            )
        stages: list[PipelineStageDTO] = []
        prior_failed: str | None = None
        for plan in run.stages:
            status = derive_stage_status(plan, now)
            duration = max(0, int((plan.planned_end - plan.planned_start).total_seconds()))
            skip_reason = None
            if status == StageDisplayStatus.OMITIDA and prior_failed:
                skip_reason = f"Omitida por fallo en {prior_failed}"
            if status == StageDisplayStatus.FALLIDA:
                prior_failed = plan.stage.value
            stages.append(
                PipelineStageDTO(
                    stage=plan.stage.value,
                    status=status.value,
                    duration_seconds=duration,
                    started_at=plan.planned_start,
                    finished_at=plan.planned_end,
                    skip_reason=skip_reason,
                )
            )
        triggered_by = None
        if run.triggered_by:
            user = self._users.get_by_id(run.triggered_by)
            if user is not None:
                triggered_by = TriggeredByDTO(id=user.id, name=user.name)
        elif run.trigger == DevopsTrigger.SEED:
            triggered_by = TriggeredByDTO(id="", name="Semilla inicial")
        return LatestPipelineResponse(
            run_id=run.id,
            is_simulated=run.is_simulated,
            trigger=run.trigger.value,
            triggered_by=triggered_by,
            created_at=run.created_at,
            status=derive_run_status(run.stages, now).value,
            computed_at=now,
            stages=stages,
        )


class TriggerPipelineUseCase:
    def __init__(
        self,
        *,
        pipeline: DevopsPipelineRepository,
        projects: ProjectRepository,
        clock: Clock,
        id_gen: IdGenerator,
        uow: UnitOfWork,
    ) -> None:
        self._pipeline = pipeline
        self._projects = projects
        self._clock = clock
        self._id_gen = id_gen
        self._uow = uow

    def execute(self, project_id: str, actor: CurrentUser) -> TriggerPipelineResponse:
        if actor.role == "developer":
            raise AccessDeniedError()
        if self._projects.get_by_id(project_id) is None:
            raise AppError("NOT_FOUND", NOT_FOUND_PROJECT, ErrorKind.NOT_FOUND)
        if not self._projects.user_can_access(project_id, actor.id, actor.role):
            raise AccessDeniedError()
        last = self._pipeline.latest_run_created_at(project_id)
        if last is not None:
            cooldown = self._pipeline.cooldown_seconds()
            now = self._clock.now()
            elapsed = (now - last).total_seconds()
            if elapsed < cooldown:
                retry = int(cooldown - elapsed)
                raise AppError(
                    "COOLDOWN_ACTIVE",
                    COOLDOWN_ACTIVE,
                    ErrorKind.RATE_LIMITED,
                    {"retry_after_seconds": str(retry)},
                )
        now = self._clock.now()
        run_id = self._id_gen.generate()
        cfg = self._pipeline.load_sim_config()
        run = build_run(
            run_id=run_id,
            project_id=project_id,
            trigger=DevopsTrigger.MANUAL,
            triggered_by=actor.id,
            created_at=now,
            cfg=cfg,
        )
        stage_ids = [self._id_gen.generate() for _ in run.stages]
        with self._uow:
            self._pipeline.save_run(run, stage_row_ids=stage_ids)
            self._uow.commit()
        return TriggerPipelineResponse(run_id=run_id, created_at=now)
