"""DevOps simulated pipeline domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DevopsTrigger(StrEnum):
    SEED = "SEED"
    MANUAL = "MANUAL"


class DevopsStage(StrEnum):
    LINT = "LINT"
    TEST = "TEST"
    BUILD = "BUILD"
    DEPLOY = "DEPLOY"


class DevopsOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StageDisplayStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_EJECUCION = "EN_EJECUCION"
    EXITOSA = "EXITOSA"
    FALLIDA = "FALLIDA"
    OMITIDA = "OMITIDA"


class RunDisplayStatus(StrEnum):
    EN_EJECUCION = "EN_EJECUCION"
    EXITOSA = "EXITOSA"
    FALLIDA = "FALLIDA"


@dataclass(frozen=True)
class SimConfig:
    success_lint: float = 0.92
    success_test: float = 0.85
    success_build: float = 0.95
    success_deploy: float = 0.98
    duration_lint_s: int = 12
    duration_test_s: int = 48
    duration_build_s: int = 30
    duration_deploy_s: int = 20


@dataclass(frozen=True)
class PipelineStagePlan:
    stage: DevopsStage
    position: int
    outcome: DevopsOutcome
    planned_start: datetime
    planned_end: datetime


@dataclass
class PipelineRun:
    id: str
    project_id: str
    trigger: DevopsTrigger
    triggered_by: str | None
    is_simulated: bool
    created_at: datetime
    stages: list[PipelineStagePlan]
