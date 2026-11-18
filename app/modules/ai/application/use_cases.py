"""Use cases for voice and text AI assistant flows (EP-10)."""

import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.intent_models import ClarificationNeeded
from app.modules.ai.application.assistant.orchestrator import AssistantOrchestrator
from app.modules.ai.application.dtos import (
    AssistantResponseStatus,
    TextGenerateResponse,
    VoiceProcessResponse,
)
from app.modules.ai.application.transcription_quality import is_low_quality_transcription
from app.modules.ai.domain import messages as msg
from app.modules.ai.domain.errors import (
    GeminiProcessingError,
    QuotaExhaustedError,
    WhisperProcessingError,
)
from app.modules.ai.domain.ports import (
    AssistantDataPort,
    GenerationPort,
    QuotaPort,
    TranscriptionPort,
)
from app.modules.ai_metrics.application.interaction_registry import (
    SOURCE_ASSISTANT_TEXT,
    SOURCE_ASSISTANT_VOICE,
    SOURCE_METRICS_QUERY,
    InteractionRegistry,
    StepRecord,
)
from app.modules.ai_metrics.infrastructure.models import AiInteractionModel
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.ai_request_trace import log_ai_stage

logger = logging.getLogger(__name__)

# Re-export for backward compatibility in tests and infrastructure imports.
__all__ = [
    "GeminiProcessingError",
    "QuotaExhaustedError",
    "WhisperProcessingError",
]


@dataclass
class VoiceProcessCommand:
    audio_bytes: bytes
    content_type: str
    duration_seconds: float | None
    project_id: str | None
    user_id: str
    user_role: str


@dataclass
class TextGenerateCommand:
    text: str
    project_id: str | None
    user_id: str
    user_role: str


@dataclass
class AssistantPipelineResult:
    response: VoiceProcessResponse
    interaction_id: str | None = None
    answer_meta: dict[str, object] | None = None


def validate_voice_audio(
    cmd: VoiceProcessCommand,
    *,
    min_bytes: int,
    max_bytes: int,
    max_seconds: float,
) -> None:
    size = len(cmd.audio_bytes)
    if size < min_bytes:
        raise AppError("EMPTY_AUDIO", msg.EMPTY_AUDIO, ErrorKind.VALIDATION)
    if size > max_bytes:
        raise AppError("AUDIO_TOO_LONG", msg.AUDIO_TOO_LONG, ErrorKind.VALIDATION)
    if cmd.duration_seconds is not None and cmd.duration_seconds > max_seconds + 0.5:
        raise AppError("AUDIO_TOO_LONG", msg.AUDIO_TOO_LONG, ErrorKind.VALIDATION)


def generate_assistant_response(
    session: Session,
    generation: GenerationPort,
    quotas: QuotaPort,
    data: AssistantDataPort,
    recognized: str,
    project_id: str | None,
    user_id: str,
    user_role: str,
    *,
    source: str = SOURCE_ASSISTANT_TEXT,
    audio_duration_ms: int = 0,
) -> AssistantPipelineResult:
    registry = InteractionRegistry(session)
    started = time.perf_counter()
    interaction_id = registry.start_pending(
        user_id=user_id,
        project_id=project_id,
        source=source,
        request_text=recognized,
        counts_as_usage=True,
        audio_duration_ms=audio_duration_ms,
    )
    orchestrator = AssistantOrchestrator(session, generation, quotas, data)
    try:
        answer = orchestrator.answer(recognized, user_id, user_role, project_id).strip()
        answer_meta = orchestrator.consume_answer_meta()
        if answer_meta and answer_meta.get("registry_source") == SOURCE_METRICS_QUERY:
            row = session.get(AiInteractionModel, interaction_id)
            if row is not None:
                row.source = SOURCE_METRICS_QUERY
                row.counts_as_usage = False
                session.flush()
            registry.record_step(
                interaction_id,
                1,
                StepRecord(step_type="METRICS_QUERY", status="SUCCESS", latency_ms=0),
            )
        else:
            registry.record_step(
                interaction_id,
                1,
                StepRecord(
                    step_type="GENERATION",
                    status="SUCCESS",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                ),
            )
        if not answer:
            registry.complete_error(
                interaction_id,
                error_code="EMPTY_ANSWER",
                total_latency_ms=int((time.perf_counter() - started) * 1000),
            )
            return AssistantPipelineResult(
                response=VoiceProcessResponse(
                    recognized_text=recognized,
                    assistant_response=None,
                    status=AssistantResponseStatus.ERROR,
                    error=msg.AI_PROCESSING_ERROR,
                ),
                interaction_id=interaction_id,
                answer_meta=answer_meta,
            )
        registry.complete_success(
            interaction_id,
            response_text=answer,
            model_id=None,
            total_latency_ms=int((time.perf_counter() - started) * 1000),
            audio_duration_ms=audio_duration_ms,
        )
        return AssistantPipelineResult(
            response=VoiceProcessResponse(
                recognized_text=recognized,
                assistant_response=answer,
                status=AssistantResponseStatus.RESPONDED,
            ),
            interaction_id=interaction_id,
            answer_meta=answer_meta,
        )
    except ClarificationNeeded as exc:
        registry.complete_success(
            interaction_id,
            response_text=exc.message,
            model_id=None,
            total_latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return AssistantPipelineResult(
            response=VoiceProcessResponse(
                recognized_text=recognized,
                assistant_response=exc.message,
                status=AssistantResponseStatus.RESPONDED,
            ),
            interaction_id=interaction_id,
        )
    except QuotaExhaustedError as exc:
        registry.complete_error(
            interaction_id,
            error_code="QUOTA_EXHAUSTED",
            total_latency_ms=int((time.perf_counter() - started) * 1000),
        )
        raise AppError(
            "FREE_QUOTA_EXHAUSTED",
            msg.FREE_QUOTA_EXHAUSTED,
            ErrorKind.RATE_LIMITED,
            fields={"service": exc.service},
        ) from exc
    except Exception:
        logger.exception("assistant_unhandled_error user_id=%s", user_id)
        registry.complete_error(
            interaction_id,
            error_code="UNHANDLED",
            total_latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return AssistantPipelineResult(
            response=VoiceProcessResponse(
                recognized_text=recognized,
                assistant_response=msg.AI_PROCESSING_ERROR,
                status=AssistantResponseStatus.ERROR,
                error=msg.AI_PROCESSING_ERROR,
            ),
            interaction_id=interaction_id,
        )


class ProcessVoiceUseCase:
    def __init__(
        self,
        session: Session,
        transcription: TranscriptionPort,
        generation: GenerationPort,
        quotas: QuotaPort,
        data: AssistantDataPort,
        *,
        min_bytes: int,
        max_bytes: int,
        max_seconds: float,
    ) -> None:
        self._session = session
        self._transcription = transcription
        self._generation = generation
        self._quotas = quotas
        self._data = data
        self._min_bytes = min_bytes
        self._max_bytes = max_bytes
        self._max_seconds = max_seconds

    def execute(self, cmd: VoiceProcessCommand) -> VoiceProcessResponse:
        validate_voice_audio(
            cmd,
            min_bytes=self._min_bytes,
            max_bytes=self._max_bytes,
            max_seconds=self._max_seconds,
        )
        try:
            if not getattr(self._transcription, "is_hybrid", False):
                self._quotas.check_and_consume("WHISPER")
            recognized = self._transcription.transcribe(cmd.audio_bytes, cmd.content_type)
        except QuotaExhaustedError as exc:
            raise AppError(
                "FREE_QUOTA_EXHAUSTED",
                msg.FREE_QUOTA_EXHAUSTED,
                ErrorKind.RATE_LIMITED,
                fields={"service": exc.service},
            ) from exc
        except WhisperProcessingError as exc:
            raise _whisper_app_error(exc) from exc

        recognized = _validated_recognized_text(recognized)

        audio_ms = int((cmd.duration_seconds or 0) * 1000)
        return generate_assistant_response(
            self._session,
            self._generation,
            self._quotas,
            self._data,
            recognized,
            cmd.project_id,
            cmd.user_id,
            cmd.user_role,
            source=SOURCE_ASSISTANT_VOICE,
            audio_duration_ms=audio_ms,
        ).response


def _whisper_app_error(exc: WhisperProcessingError) -> AppError:
    if str(exc) in {"no_speech", "invalid_payload"}:
        return AppError("VOICE_NOT_UNDERSTOOD", msg.VOICE_NOT_UNDERSTOOD, ErrorKind.VALIDATION)
    return AppError("AI_PROCESSING_ERROR", msg.AI_PROCESSING_ERROR, ErrorKind.UNAVAILABLE)


def _validated_recognized_text(recognized: str) -> str:
    recognized = recognized.strip()
    if not recognized:
        raise AppError("EMPTY_AUDIO", msg.EMPTY_AUDIO, ErrorKind.VALIDATION)
    if is_low_quality_transcription(recognized):
        raise AppError("VOICE_NOT_UNDERSTOOD", msg.VOICE_NOT_UNDERSTOOD, ErrorKind.VALIDATION)
    return recognized


class TranscribeVoiceUseCase:
    """Whisper-only step for voice chat (transcription shown before Gemini)."""

    def __init__(
        self,
        transcription: TranscriptionPort,
        quotas: QuotaPort,
        *,
        min_bytes: int,
        max_bytes: int,
        max_seconds: float,
    ) -> None:
        self._transcription = transcription
        self._quotas = quotas
        self._min_bytes = min_bytes
        self._max_bytes = max_bytes
        self._max_seconds = max_seconds

    def execute(self, cmd: VoiceProcessCommand) -> str:
        validate_voice_audio(
            cmd,
            min_bytes=self._min_bytes,
            max_bytes=self._max_bytes,
            max_seconds=self._max_seconds,
        )
        try:
            if not getattr(self._transcription, "is_hybrid", False):
                self._quotas.check_and_consume("WHISPER")
            recognized = self._transcription.transcribe(cmd.audio_bytes, cmd.content_type)
        except QuotaExhaustedError as exc:
            raise AppError(
                "FREE_QUOTA_EXHAUSTED",
                msg.FREE_QUOTA_EXHAUSTED,
                ErrorKind.RATE_LIMITED,
                fields={"service": exc.service},
            ) from exc
        except WhisperProcessingError as exc:
            raise _whisper_app_error(exc) from exc
        return _validated_recognized_text(recognized)


class GenerateTextUseCase:
    def __init__(
        self,
        session: Session,
        generation: GenerationPort,
        quotas: QuotaPort,
        data: AssistantDataPort,
    ) -> None:
        self._session = session
        self._generation = generation
        self._quotas = quotas
        self._data = data

    def execute(self, cmd: TextGenerateCommand) -> TextGenerateResponse:
        log_ai_stage("generate_text_use_case_start", user_id=cmd.user_id)
        pipeline = generate_assistant_response(
            self._session,
            self._generation,
            self._quotas,
            self._data,
            cmd.text.strip(),
            cmd.project_id,
            cmd.user_id,
            cmd.user_role,
        )
        result = pipeline.response
        meta = pipeline.answer_meta or {}
        response = TextGenerateResponse(
            recognized_text=cmd.text.strip(),
            assistant_response=result.assistant_response,
            status=result.status,
            error=result.error,
            intent=str(meta["intent"]) if meta.get("intent") is not None else None,
            period=str(meta["period"]) if meta.get("period") is not None else None,
            scope=str(meta["scope"]) if meta.get("scope") is not None else None,
            data=meta.get("data") if isinstance(meta.get("data"), dict) else None,
            panel_link=str(meta["panel_link"]) if meta.get("panel_link") is not None else None,
            clarification=(
                str(meta["clarification"]) if meta.get("clarification") is not None else None
            ),
            interaction_id=pipeline.interaction_id,
        )
        log_ai_stage(
            "generate_text_use_case_done",
            status=response.status.value,
            has_answer=bool(response.assistant_response),
        )
        return response
