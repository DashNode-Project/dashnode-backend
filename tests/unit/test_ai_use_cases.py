"""Unit tests for AI voice/text use cases (HU 91, 93, 95)."""

import pytest

from app.modules.ai.application.use_cases import (
    GeminiProcessingError,
    ProcessVoiceUseCase,
    QuotaExhaustedError,
    VoiceProcessCommand,
    WhisperProcessingError,
)
from app.modules.ai.domain.ports import ProjectAiContext
from app.shared.domain.errors import AppError


class FakeTranscription:
    def __init__(self, text: str = "consulta de prueba") -> None:
        self.text = text

    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        return self.text


class FakeGeneration:
    def __init__(self, answer: str = "respuesta", fail: bool = False) -> None:
        self.answer = answer
        self.fail = fail

    def generate(self, prompt: str) -> str:
        if self.fail:
            raise GeminiProcessingError("fail")
        return self.answer


class FakeQuota:
    def check_and_consume(self, service: str) -> None:
        return None


class ExhaustedQuota:
    def check_and_consume(self, service: str) -> None:
        raise QuotaExhaustedError(service)


class FakeContext:
    def build_context(
        self, project_id: str | None, user_id: str, user_role: str
    ) -> ProjectAiContext:
        return ProjectAiContext("P", "D", "S", ())


def _use_case(
    transcription: FakeTranscription | None = None,
    generation: FakeGeneration | None = None,
    quotas: FakeQuota | ExhaustedQuota | None = None,
    *,
    transcription_override: object | None = None,
) -> ProcessVoiceUseCase:
    return ProcessVoiceUseCase(
        transcription=transcription_override or transcription or FakeTranscription(),  # type: ignore[arg-type]
        generation=generation or FakeGeneration(),
        quotas=quotas or FakeQuota(),
        project_context=FakeContext(),
        min_bytes=10,
        max_bytes=100_000,
        max_seconds=60.0,
    )


def test_empty_audio_rejected() -> None:
    uc = _use_case()
    with pytest.raises(AppError) as exc:
        uc.execute(
            VoiceProcessCommand(b"x", "audio/webm", None, None, "u1", "developer"),
        )
    assert exc.value.code == "EMPTY_AUDIO"


def test_voice_flow_success() -> None:
    result = _use_case().execute(
        VoiceProcessCommand(b"0" * 20, "audio/webm", 2.0, None, "u1", "developer"),
    )
    assert result.status == "RESPONDED"
    assert result.recognized_text == "consulta de prueba"
    assert result.assistant_response == "respuesta"


def test_partial_gemini_failure_keeps_transcription() -> None:
    result = _use_case(generation=FakeGeneration(fail=True)).execute(
        VoiceProcessCommand(b"0" * 20, "audio/webm", 1.0, None, "u1", "developer"),
    )
    assert result.recognized_text == "consulta de prueba"
    assert result.assistant_response is None
    assert result.error is not None


def test_quota_exhausted_maps_to_app_error() -> None:
    uc = _use_case(quotas=ExhaustedQuota())
    with pytest.raises(AppError) as exc:
        uc.execute(
            VoiceProcessCommand(b"0" * 20, "audio/webm", 1.0, None, "u1", "developer"),
        )
    assert exc.value.code == "FREE_QUOTA_EXHAUSTED"


def test_whisper_failure_is_unavailable() -> None:
    class FailWhisper:
        def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
            raise WhisperProcessingError("x")

    uc = _use_case(transcription_override=FailWhisper())
    with pytest.raises(AppError) as exc:
        uc.execute(
            VoiceProcessCommand(b"0" * 20, "audio/webm", 1.0, None, "u1", "developer"),
        )
    assert exc.value.code == "AI_PROCESSING_ERROR"
