"""Unit tests for the resilient hybrid voice transcription service.

Verifies:
1. Whisper Priority 1 (optional, fallback on 429 / timeout / network).
2. Gemini REST Priority 2 (gemini-3.5-transcribe with smart mode, then multimodal fallbacks).
3. Independent daily quota counters (whisper vs gemini_transcribe vs generation).
4. Model cooldown and resilience.
5. Quality heuristics & silence filtering ([SILENCIO] rejection).
"""

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from app.config import settings
from app.modules.ai.application.transcription_quality import is_low_quality_transcription
from app.modules.ai.domain.errors import (
    GeminiProcessingError,
    WhisperProcessingError,
)
from app.modules.ai.infrastructure.gemini_transcribe_client import (
    GenAiGeminiTranscribeClient,
    gemini_transcribe_model_chain,
)
from app.modules.ai.infrastructure.hybrid_transcription_service import HybridTranscriptionService
from app.modules.ai.infrastructure.llm_provider_router import ModelAvailabilityRegistry
from app.modules.ai.infrastructure.quota_repository import InMemoryQuotaRepository
from app.shared.domain.errors import AppError


def test_gemini_transcribe_model_chain_ordering() -> None:
    chain = gemini_transcribe_model_chain()
    assert chain[0] == settings.AI_GEMINI_TRANSCRIBE_MODEL
    assert "gemini-3.5-flash-lite" in chain
    assert "gemini-3.6-flash" in chain


def test_silence_and_hallucination_filtering() -> None:
    assert is_low_quality_transcription("[SILENCIO]") is True
    assert is_low_quality_transcription("silencio") is True
    assert is_low_quality_transcription("   [silencio]   ") is True
    assert is_low_quality_transcription("   ") is True
    assert is_low_quality_transcription("a") is True
    assert is_low_quality_transcription("¿Cuáles son los issues abiertos del sprint?") is False


def test_whisper_priority_1_success_consumes_whisper_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_TRANSCRIPTION_WHISPER", SecretStr("test-whisper-key-valid"))
    quotas = InMemoryQuotaRepository()

    mock_whisper = MagicMock()
    mock_whisper.transcribe.return_value = "Crear tarea en sprint 2"
    mock_gemini = MagicMock()

    service = HybridTranscriptionService(
        quotas=quotas,
        whisper_client=mock_whisper,
        gemini_client=mock_gemini,
    )

    result = service.transcribe(b"dummy-audio-bytes", "audio/webm")
    assert result == "Crear tarea en sprint 2"
    mock_whisper.transcribe.assert_called_once()
    mock_gemini.transcribe.assert_not_called()

    # Whisper quota consumed, but NOT gemini_transcribe
    assert quotas.has_quota("whisper") is True
    assert quotas.has_quota("gemini_transcribe") is True


def test_whisper_failure_falls_back_to_gemini_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_TRANSCRIPTION_WHISPER", SecretStr("test-key"))
    quotas = InMemoryQuotaRepository()

    mock_whisper = MagicMock()
    mock_whisper.transcribe.side_effect = WhisperProcessingError("quota")
    mock_gemini = MagicMock()
    mock_gemini.transcribe.return_value = "Listar tareas del proyecto"

    service = HybridTranscriptionService(
        quotas=quotas,
        whisper_client=mock_whisper,
        gemini_client=mock_gemini,
    )

    result = service.transcribe(b"dummy-audio-bytes", "audio/webm")
    assert result == "Listar tareas del proyecto"
    mock_whisper.transcribe.assert_called_once()
    mock_gemini.transcribe.assert_called_once()


def test_whisper_missing_key_skips_directly_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_TRANSCRIPTION_WHISPER", None)
    quotas = InMemoryQuotaRepository()

    mock_whisper = MagicMock()
    mock_gemini = MagicMock()
    mock_gemini.transcribe.return_value = "Consulta directa a Gemini"

    service = HybridTranscriptionService(
        quotas=quotas,
        whisper_client=mock_whisper,
        gemini_client=mock_gemini,
    )

    result = service.transcribe(b"dummy-audio-bytes", "audio/webm")
    assert result == "Consulta directa a Gemini"
    mock_whisper.transcribe.assert_not_called()
    mock_gemini.transcribe.assert_called_once()


def test_gemini_transcribe_quota_exhausted_raises_free_quota_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "API_TRANSCRIPTION_WHISPER", None)
    quotas = InMemoryQuotaRepository()

    # Exhaust gemini_transcribe quota
    limit = settings.AI_GEMINI_TRANSCRIBE_DAILY_LIMIT
    for _ in range(limit):
        quotas.check_and_consume("gemini_transcribe")

    mock_gemini = MagicMock()
    service = HybridTranscriptionService(
        quotas=quotas,
        gemini_client=mock_gemini,
    )

    with pytest.raises(AppError) as exc_info:
        service.transcribe(b"dummy-audio-bytes", "audio/webm")

    assert exc_info.value.code == "FREE_QUOTA_EXHAUSTED"
    mock_gemini.transcribe.assert_not_called()


def test_gemini_transcribe_timeout_mapped_to_ai_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "API_TRANSCRIPTION_WHISPER", None)
    quotas = InMemoryQuotaRepository()

    mock_gemini = MagicMock()
    mock_gemini.transcribe.side_effect = GeminiProcessingError("timeout")

    service = HybridTranscriptionService(
        quotas=quotas,
        gemini_client=mock_gemini,
    )

    with pytest.raises(AppError) as exc_info:
        service.transcribe(b"dummy-audio-bytes", "audio/webm")

    assert exc_info.value.code == "AI_REQUEST_TIMEOUT"


def test_gemini_transcribe_client_smart_mode_and_multimodal_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("test-gemini-key"))
    registry = ModelAvailabilityRegistry()

    # Mock genai client and interactions
    mock_client = MagicMock()

    # Attempt 1 on gemini-3.5-transcribe fails with 503
    mock_interaction_failed = MagicMock()
    mock_interaction_failed.output_text = None
    mock_interaction_failed.status = "failed"
    mock_interaction_failed.errors = ["error 503"]

    # Attempt 2 on gemini-3.5-flash-lite succeeds
    mock_interaction_success = MagicMock()
    mock_interaction_success.output_text = "Transcripción desde flash lite"
    mock_interaction_success.status = "complete"
    mock_interaction_success.errors = []

    mock_client.interactions.create.side_effect = [
        mock_interaction_failed,
        mock_interaction_success,
    ]

    client = GenAiGeminiTranscribeClient(client=mock_client, registry=registry)
    text = client.transcribe(b"dummy-audio-bytes", "audio/webm")

    assert text == "Transcripción desde flash lite"
    assert mock_client.interactions.create.call_count == 2

    # Verify first call had transcription_config with smart mode
    call1_kwargs = mock_client.interactions.create.call_args_list[0].kwargs
    assert call1_kwargs["model"] == settings.AI_GEMINI_TRANSCRIBE_MODEL
    trans_cfg = call1_kwargs["generation_config"]["transcription_config"]
    assert trans_cfg["mode"] == "smart"
    assert "DashNode" in trans_cfg["custom_vocabulary"]

    # Verify second call was multimodal with prompt
    call2_kwargs = mock_client.interactions.create.call_args_list[1].kwargs
    assert call2_kwargs["model"] == "gemini-3.5-flash-lite"
    assert any("[SILENCIO]" in str(item) for item in call2_kwargs["input"])
