"""Use cases for voice and text AI assistant flows (EP-10)."""

import logging
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
) -> VoiceProcessResponse:
    orchestrator = AssistantOrchestrator(session, generation, quotas, data)
    try:
        answer = orchestrator.answer(recognized, user_id, user_role, project_id).strip()
    except ClarificationNeeded as exc:
        return VoiceProcessResponse(
            recognized_text=recognized,
            assistant_response=exc.message,
            status=AssistantResponseStatus.RESPONDED,
        )
    except QuotaExhaustedError as exc:
        raise AppError(
            "FREE_QUOTA_EXHAUSTED",
            msg.FREE_QUOTA_EXHAUSTED,
            ErrorKind.RATE_LIMITED,
            fields={"service": exc.service},
        ) from exc
    except Exception:
        logger.exception("assistant_unhandled_error user_id=%s", user_id)
        return VoiceProcessResponse(
            recognized_text=recognized,
            assistant_response=msg.AI_PROCESSING_ERROR,
            status=AssistantResponseStatus.ERROR,
            error=msg.AI_PROCESSING_ERROR,
        )

    if not answer:
        return VoiceProcessResponse(
            recognized_text=recognized,
            assistant_response=None,
            status=AssistantResponseStatus.ERROR,
            error=msg.AI_PROCESSING_ERROR,
        )
    return VoiceProcessResponse(
        recognized_text=recognized,
        assistant_response=answer,
        status=AssistantResponseStatus.RESPONDED,
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

        return generate_assistant_response(
            self._session,
            self._generation,
            self._quotas,
            self._data,
            recognized,
            cmd.project_id,
            cmd.user_id,
            cmd.user_role,
        )


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
        result = generate_assistant_response(
            self._session,
            self._generation,
            self._quotas,
            self._data,
            cmd.text.strip(),
            cmd.project_id,
            cmd.user_id,
            cmd.user_role,
        )
        response = TextGenerateResponse(
            recognized_text=cmd.text.strip(),
            assistant_response=result.assistant_response,
            status=result.status,
            error=result.error,
        )
        log_ai_stage(
            "generate_text_use_case_done",
            status=response.status.value,
            has_answer=bool(response.assistant_response),
        )
        return response
