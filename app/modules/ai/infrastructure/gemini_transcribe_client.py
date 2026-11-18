"""Google Gemini voice transcription client (official google-genai SDK, Interactions API REST).

Resilient transcription using gemini-3.5-transcribe with multimodal fallbacks.
In-memory processing only; no disk persistence.
"""

from __future__ import annotations

import base64
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError, QuotaExhaustedError
from app.modules.ai.infrastructure.gemini_client import (
    _gemini_http_options,
    _gemini_timeout_seconds,
    _map_api_error,
    _normalize_model_id,
    resolve_gemini_api_key,
)
from app.modules.ai.infrastructure.llm_provider_router import ModelAvailabilityRegistry
from app.shared.infrastructure.ai_request_trace import log_ai_stage

logger = logging.getLogger(__name__)

DEFAULT_TRANSCRIBE_MODEL = "gemini-3.5-transcribe"
_STRICT_MULTIMODAL_PROMPT = (
    "Transcribe el audio de manera literal y exacta en su idioma original "
    "(principalmente español). No agregues comentarios, explicaciones, ni "
    "introducciones. Si el audio no contiene voz humana perceptible o es "
    "solo ruido/silencio, responde únicamente con '[SILENCIO]'."
)

_CUSTOM_VOCABULARY = ["DashNode", "Sprint", "Backlog", "Kanban", "HU"]

_transcribe_registry = ModelAvailabilityRegistry()


def gemini_transcribe_model_chain() -> tuple[str, ...]:
    """Primary transcribe model first, then configured fallbacks (deduplicated)."""
    seen: set[str] = set()
    chain: list[str] = []
    primary = settings.AI_GEMINI_TRANSCRIBE_MODEL or DEFAULT_TRANSCRIBE_MODEL
    raw_models = [primary, *settings.AI_GEMINI_TRANSCRIBE_FALLBACK_MODELS.split(",")]
    for raw in raw_models:
        model_id = _normalize_model_id(raw.strip())
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        chain.append(model_id)
    return tuple(chain or (DEFAULT_TRANSCRIBE_MODEL,))


class GenAiGeminiTranscribeClient:
    """TranscriptionPort adapter using client.interactions.create() REST."""

    def __init__(
        self,
        client: genai.Client | None = None,
        registry: ModelAvailabilityRegistry | None = None,
    ) -> None:
        self._client = client
        self._registry = registry or _transcribe_registry

    def _build_client(self) -> genai.Client:
        if self._client is not None:
            return self._client
        key = resolve_gemini_api_key()
        if not key:
            raise GeminiProcessingError("missing_api_key")
        return genai.Client(api_key=key, http_options=_gemini_http_options())

    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        wall_limit = _gemini_timeout_seconds() + 5.0
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemini-transcribe")
        future = pool.submit(self._transcribe_sync_inner, audio_bytes, content_type)
        try:
            return future.result(timeout=wall_limit)
        except FuturesTimeoutError as exc:
            log_ai_stage("gemini_transcribe_wall_clock_timeout", limit_s=wall_limit)
            raise GeminiProcessingError("timeout") from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _transcribe_sync_inner(self, audio_bytes: bytes, content_type: str) -> str:
        client = self._build_client()
        chain = gemini_transcribe_model_chain()
        available_models = [m for m in chain if self._registry.is_available(m)]
        if not available_models:
            log_ai_stage("gemini_transcribe_all_cooled_down")
            raise GeminiProcessingError("all_models_cooled_down")

        mime = content_type or "audio/webm"
        if "webm" in mime.lower():
            norm_mime = "audio/webm"
        elif "wav" in mime.lower():
            norm_mime = "audio/wav"
        elif "mp3" in mime.lower():
            norm_mime = "audio/mp3"
        elif "ogg" in mime.lower():
            norm_mime = "audio/ogg"
        else:
            norm_mime = "audio/webm"

        b64_data = base64.b64encode(audio_bytes).decode("utf-8")
        audio_content: dict[str, Any] = {
            "type": "audio",
            "data": b64_data,
            "mime_type": norm_mime,
        }

        last_error: Exception | None = None
        has_quota_error = False

        for attempt_index, model_id in enumerate(available_models):
            started = time.perf_counter()
            log_ai_stage("gemini_transcribe_attempt", model=model_id, attempt=attempt_index)
            is_transcribe_specialized = "transcribe" in model_id.lower()

            try:
                if is_transcribe_specialized:
                    input_payload: Any = [audio_content]
                    gen_config: dict[str, Any] = {
                        "transcription_config": {
                            "mode": "smart",
                            "custom_vocabulary": _CUSTOM_VOCABULARY,
                        }
                    }
                else:
                    input_payload = [
                        {"type": "text", "text": _STRICT_MULTIMODAL_PROMPT},
                        audio_content,
                    ]
                    gen_config = {}

                timeout = _gemini_timeout_seconds()
                interaction: Any = client.interactions.create(
                    model=model_id,
                    input=input_payload,
                    stream=False,
                    timeout=timeout,
                    generation_config=gen_config or None,
                )

                output_text = getattr(interaction, "output_text", None)
                candidates = getattr(interaction, "candidates", None)
                if not output_text and candidates:
                    cand = candidates[0]
                    content = getattr(cand, "content", None)
                    if content and getattr(content, "parts", None):
                        output_text = "".join(
                            getattr(p, "text", "")
                            for p in content.parts
                            if getattr(p, "text", None)
                        )

                if isinstance(output_text, str) and output_text.strip():
                    text = output_text.strip()
                    self._registry.mark_success(model_id)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    log_ai_stage(
                        "gemini_transcribe_success",
                        model=model_id,
                        chars=len(text),
                        latency_ms=f"{elapsed_ms:.1f}",
                    )
                    return text

                raise GeminiProcessingError("empty_response")

            except genai_errors.APIError as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                mapped = _map_api_error(exc)
                code = str(mapped)
                if code == "quota":
                    has_quota_error = True
                self._registry.mark_failure(model_id, mapped)
                last_error = mapped
                logger.warning(
                    "gemini_transcribe_model_failed model=%s latency_ms=%.1f error=%s",
                    model_id,
                    elapsed_ms,
                    code,
                )
            except httpx.TimeoutException:
                elapsed_ms = (time.perf_counter() - started) * 1000
                err = GeminiProcessingError("timeout")
                self._registry.mark_failure(model_id, err)
                last_error = err
                logger.warning(
                    "gemini_transcribe_timeout model=%s latency_ms=%.1f", model_id, elapsed_ms
                )
            except (httpx.HTTPError, GeminiProcessingError, Exception) as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                err = (
                    exc
                    if isinstance(exc, GeminiProcessingError)
                    else GeminiProcessingError("network")
                )
                self._registry.mark_failure(model_id, err)
                last_error = err
                logger.warning(
                    "gemini_transcribe_error model=%s latency_ms=%.1f error=%s",
                    model_id,
                    elapsed_ms,
                    exc,
                )

        if has_quota_error:
            raise QuotaExhaustedError("gemini_transcribe")
        if isinstance(last_error, GeminiProcessingError) and str(last_error) == "timeout":
            raise GeminiProcessingError("timeout")
        raise GeminiProcessingError("AI_GEMINI_UNAVAILABLE")
