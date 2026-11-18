"""DevOps repository ports."""

from __future__ import annotations

from typing import Protocol

from app.modules.devops.domain.entities import PipelineRun, SimConfig


class DevopsPipelineRepository(Protocol):
    def load_sim_config(self) -> SimConfig: ...

    def cooldown_seconds(self) -> int: ...

    def latest_run_created_at(self, project_id: str) -> object | None: ...

    def save_run(self, run: PipelineRun, *, stage_row_ids: list[str]) -> None: ...

    def get_latest(self, project_id: str) -> PipelineRun | None: ...
