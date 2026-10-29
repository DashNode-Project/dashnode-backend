"""Use cases for voice and text AI assistant flows (EP-10)."""

from dataclasses import dataclass

from app.modules.ai.application.dtos import (
    AssistantResponseStatus,
    TextGenerateResponse,
    VoiceProcessResponse,
)
from app.modules.ai.application.prompt_builder import build_assistant_prompt
from app.modules.ai.application.transcription_quality import is_low_quality_transcription
from app.modules.ai.domain import messages as msg
from app.modules.ai.domain.ports import (
    GenerationPort,
    ProjectContextPort,
    QuotaPort,
    TranscriptionPort,
)
from app.shared.domain.errors import AppError, ErrorKind


class WhisperProcessingError(Exception):
    pass


class GeminiProcessingError(Exception):
    pass


class QuotaExhaustedError(Exception):
    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__(service)


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
    generation: GenerationPort,
    quotas: QuotaPort,
    project_context: ProjectContextPort,
    recognized: str,
    project_id: str | None,
    user_id: str,
    user_role: str,
) -> VoiceProcessResponse:
    context = project_context.build_context(project_id, user_id, user_role)
    prompt = build_assistant_prompt(context, recognized)
    try:
        quotas.check_and_consume("GEMINI")
        answer = generation.generate(prompt).strip()
    except QuotaExhaustedError as exc:
        raise AppError(
            "FREE_QUOTA_EXHAUSTED",
            msg.FREE_QUOTA_EXHAUSTED,
            ErrorKind.RATE_LIMITED,
            fields={"service": exc.service},
        ) from exc
    except GeminiProcessingError:
        return VoiceProcessResponse(
            recognized_text=recognized,
            assistant_response=None,
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
        transcription: TranscriptionPort,
        generation: GenerationPort,
        quotas: QuotaPort,
        project_context: ProjectContextPort,
        *,
        min_bytes: int,
        max_bytes: int,
        max_seconds: float,
    ) -> None:
        self._transcription = transcription
        self._generation = generation
        self._quotas = quotas
        self._project_context = project_context
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
            raise AppError(
                "AI_PROCESSING_ERROR",
                msg.AI_PROCESSING_ERROR,
                ErrorKind.UNAVAILABLE,
            ) from exc

        recognized = _validated_recognized_text(recognized)

        return generate_assistant_response(
            self._generation,
            self._quotas,
            self._project_context,
            recognized,
            cmd.project_id,
            cmd.user_id,
            cmd.user_role,
        )

def _validated_recognized_text(recognized: str) -> str:
    recognized = recognized.strip()
    if not recognized or is_low_quality_transcription(recognized):
        raise AppError("EMPTY_AUDIO", msg.EMPTY_AUDIO, ErrorKind.VALIDATION)
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
            raise AppError(
                "AI_PROCESSING_ERROR",
                msg.AI_PROCESSING_ERROR,
                ErrorKind.UNAVAILABLE,
            ) from exc
        return _validated_recognized_text(recognized)


class GenerateTextUseCase:
    def __init__(
        self,
        generation: GenerationPort,
        quotas: QuotaPort,
        project_context: ProjectContextPort,
    ) -> None:
        self._generation = generation
        self._quotas = quotas
        self._project_context = project_context

    def execute(self, cmd: TextGenerateCommand) -> TextGenerateResponse:
        result = generate_assistant_response(
            self._generation,
            self._quotas,
            self._project_context,
            cmd.text.strip(),
            cmd.project_id,
            cmd.user_id,
            cmd.user_role,
        )
        return TextGenerateResponse(
            recognized_text=cmd.text.strip(),
            assistant_response=result.assistant_response,
            status=result.status,
            error=result.error,
        )
