"""Hybrid resilient voice transcription service (Whisper Priority 1 -> Gemini REST Priority 2).

@sad EP-10 AI Assistant, Anexo D
"""

from __future__ import annotations

import logging

from app.config import settings
from app.modules.ai.domain import messages as ai_msg
from app.modules.ai.domain.errors import (
    GeminiProcessingError,
    QuotaExhaustedError,
    WhisperProcessingError,
)
from app.modules.ai.domain.ports import QuotaPort, TranscriptionPort
from app.modules.ai.infrastructure.gemini_transcribe_client import GenAiGeminiTranscribeClient
from app.modules.ai.infrastructure.whisper_client import HttpWhisperClient
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.ai_request_trace import log_ai_stage

logger = logging.getLogger(__name__)


class HybridTranscriptionService:
    """Orchestrates Whisper (primary when configured) and Gemini REST fallback."""

    is_hybrid: bool = True

    def __init__(
        self,
        quotas: QuotaPort,
        whisper_client: TranscriptionPort | None = None,
        gemini_client: TranscriptionPort | None = None,
    ) -> None:
        self._quotas = quotas
        self._whisper = whisper_client or HttpWhisperClient()
        self._gemini = gemini_client or GenAiGeminiTranscribeClient()

    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        # --- Priority 1: Whisper (optional) ---
        whisper_key = settings.API_TRANSCRIPTION_WHISPER
        has_whisper_key = bool(whisper_key and whisper_key.get_secret_value().strip())
        has_quota_fn = getattr(self._quotas, "has_quota", None)
        whisper_has_quota = bool(has_quota_fn("whisper")) if callable(has_quota_fn) else True

        if has_whisper_key and whisper_has_quota:
            log_ai_stage("transcribe_attempt_whisper")
            try:
                recognized = self._whisper.transcribe(audio_bytes, content_type)
                # Consume quota only on successful transcription attempt
                self._quotas.check_and_consume("whisper")
                log_ai_stage("transcribe_whisper_success", chars=len(recognized))
                return recognized
            except (WhisperProcessingError, Exception) as exc:
                logger.warning(
                    "Whisper transcription failed (%s); falling back to Gemini REST chain "
                    "without error to user",
                    exc,
                )
                log_ai_stage("transcribe_whisper_fallback_to_gemini", error=str(exc))
        else:
            log_ai_stage(
                "transcribe_whisper_skipped",
                has_key=has_whisper_key,
                has_quota=whisper_has_quota,
            )

        # --- Priority 2: Gemini REST Chain ---
        log_ai_stage("transcribe_attempt_gemini")
        try:
            self._quotas.check_and_consume("gemini_transcribe")
        except QuotaExhaustedError as exc:
            raise AppError(
                "FREE_QUOTA_EXHAUSTED",
                ai_msg.FREE_QUOTA_EXHAUSTED,
                ErrorKind.RATE_LIMITED,
                fields={"service": exc.service},
            ) from exc

        try:
            recognized = self._gemini.transcribe(audio_bytes, content_type)
            log_ai_stage("transcribe_gemini_success", chars=len(recognized))
            return recognized
        except QuotaExhaustedError as exc:
            raise AppError(
                "FREE_QUOTA_EXHAUSTED",
                ai_msg.FREE_QUOTA_EXHAUSTED,
                ErrorKind.RATE_LIMITED,
                fields={"service": exc.service},
            ) from exc
        except GeminiProcessingError as exc:
            code = str(exc)
            if code == "timeout":
                raise AppError(
                    "AI_REQUEST_TIMEOUT",
                    ai_msg.AI_REQUEST_TIMEOUT,
                    ErrorKind.UNAVAILABLE,
                ) from exc
            raise AppError(
                "AI_GEMINI_UNAVAILABLE",
                ai_msg.AI_GEMINI_UNAVAILABLE,
                ErrorKind.UNAVAILABLE,
            ) from exc
        except Exception as exc:
            logger.error("Gemini transcribe unexpected error: %s", exc)
            raise AppError(
                "AI_GEMINI_UNAVAILABLE",
                ai_msg.AI_GEMINI_UNAVAILABLE,
                ErrorKind.UNAVAILABLE,
            ) from exc
