"""Fail-closed AI interaction registry (EP-13).

Creates a PENDING row before any provider call; completes as SUCCESS or ERROR.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, timedelta

from sqlalchemy.orm import Session

from app.modules.ai_metrics.infrastructure.models import (
    AiInteractionModel,
    AiInteractionStepModel,
)
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator

SOURCE_ASSISTANT_TEXT = "ASSISTANT_TEXT"
SOURCE_ASSISTANT_VOICE = "ASSISTANT_VOICE"
SOURCE_ISSUE_ANALYSIS = "ISSUE_ANALYSIS"
SOURCE_METRICS_QUERY = "METRICS_QUERY"

STATUS_PENDING = "PENDING"
STATUS_SUCCESS = "SUCCESS"
STATUS_ERROR = "ERROR"

RETENTION_DAYS = 730  # v1: purge job deferred; expires_at set only.


@dataclass(slots=True)
class StepRecord:
    step_type: str
    status: str
    model_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    audio_duration_ms: int = 0
    latency_ms: int = 0


class InteractionRegistry:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._ids = UuidGenerator()
        self._clock = SystemClock()

    def start_pending(
        self,
        *,
        user_id: str,
        project_id: str | None,
        source: str,
        request_text: str | None,
        counts_as_usage: bool = True,
        audio_duration_ms: int = 0,
    ) -> str:
        """Persist PENDING and flush before external I/O (fail-closed)."""
        now = self._clock.now().astimezone(UTC)
        interaction_id = self._ids.generate()
        row = AiInteractionModel(
            id=interaction_id,
            user_id=user_id,
            project_id=project_id,
            source=source,
            status=STATUS_PENDING,
            request_text=request_text,
            response_text=None,
            model_id=None,
            input_tokens=0,
            output_tokens=0,
            total_latency_ms=0,
            audio_duration_ms=max(0, audio_duration_ms),
            counts_as_usage=counts_as_usage,
            error_code=None,
            created_at=now,
            completed_at=None,
            expires_at=now + timedelta(days=RETENTION_DAYS),
        )
        self._session.add(row)
        self._session.flush()
        return interaction_id

    def record_step(self, interaction_id: str, order: int, step: StepRecord) -> None:
        now = self._clock.now().astimezone(UTC)
        self._session.add(
            AiInteractionStepModel(
                id=self._ids.generate(),
                interaction_id=interaction_id,
                step_order=order,
                step_type=step.step_type,
                status=step.status,
                model_id=step.model_id,
                input_tokens=max(0, step.input_tokens),
                output_tokens=max(0, step.output_tokens),
                audio_duration_ms=max(0, step.audio_duration_ms),
                latency_ms=max(0, step.latency_ms),
                created_at=now,
            )
        )
        self._session.flush()

    def complete_success(
        self,
        interaction_id: str,
        *,
        response_text: str | None,
        model_id: str | None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_latency_ms: int = 0,
        audio_duration_ms: int | None = None,
    ) -> None:
        row = self._session.get(AiInteractionModel, interaction_id)
        if row is None:
            return
        now = self._clock.now().astimezone(UTC)
        row.status = STATUS_SUCCESS
        row.response_text = response_text
        row.model_id = model_id
        row.input_tokens = max(0, input_tokens)
        row.output_tokens = max(0, output_tokens)
        row.total_latency_ms = max(0, total_latency_ms)
        if audio_duration_ms is not None:
            row.audio_duration_ms = max(0, audio_duration_ms)
        row.completed_at = now
        self._session.flush()

    def complete_error(
        self,
        interaction_id: str,
        *,
        error_code: str,
        response_text: str | None = None,
        total_latency_ms: int = 0,
    ) -> None:
        row = self._session.get(AiInteractionModel, interaction_id)
        if row is None:
            return
        now = self._clock.now().astimezone(UTC)
        row.status = STATUS_ERROR
        row.error_code = error_code
        row.response_text = response_text
        row.total_latency_ms = max(0, total_latency_ms)
        row.completed_at = now
        self._session.flush()

    def link_analysis(self, analysis_id: str, interaction_id: str) -> None:
        from app.modules.fixes.infrastructure.models import AiAnalysisModel

        analysis = self._session.get(AiAnalysisModel, analysis_id)
        if analysis is not None:
            analysis.interaction_id = interaction_id
            self._session.flush()
