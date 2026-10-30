"""Google Gemini text generation (official google-genai SDK, Interactions API)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import TYPE_CHECKING, Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai.types import HttpOptionsDict

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError
from app.shared.infrastructure.ai_request_trace import log_ai_stage

if TYPE_CHECKING:
    from google.genai._gaos.types.interactions.interaction import Interaction

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
_RETRYABLE_STATUS = {502, 503, 504}
_INTERPRETATION_GENERATION_CONFIG: dict[str, object] = {
    "thinking_level": "low",
    "max_output_tokens": 512,
}


def _gemini_timeout_seconds() -> float:
    return float(settings.AI_GEMINI_TIMEOUT_SECONDS)


def _gemini_http_options() -> HttpOptionsDict:
    timeout_ms = int(_gemini_timeout_seconds() * 1000)
    return {
        "timeout": timeout_ms,
        "retry_options": {
            "attempts": 2,
            "initial_delay": 0.4,
            "max_delay": 2.0,
            "http_status_codes": [408, 429, 500, 502, 503, 504],
        },
    }


def _normalize_model_id(model: str) -> str:
    name = model.strip()
    if name.startswith("models/"):
        name = name.removeprefix("models/")
    return name or DEFAULT_GEMINI_MODEL


def resolve_gemini_api_key() -> str | None:
    """Prefer GEMINI_API_KEY; fall back to legacy API_GEMINI."""
    if settings.GEMINI_API_KEY is not None:
        value = settings.GEMINI_API_KEY.get_secret_value().strip()
        if value:
            return value
    if settings.API_GEMINI is not None:
        value = settings.API_GEMINI.get_secret_value().strip()
        if value:
            return value
    return None


def _map_api_error(exc: genai_errors.APIError) -> GeminiProcessingError:
    code = getattr(exc, "code", None) or 0
    message = getattr(exc, "message", None) or str(exc)
    logger.warning(
        "gemini_api_error_mapped http_code=%s error_type=%s message_len=%s",
        code,
        type(exc).__name__,
        len(str(message)),
    )
    if code == 401:
        return GeminiProcessingError("auth_401")
    if code == 403:
        return GeminiProcessingError("forbidden_403")
    if code == 404:
        return GeminiProcessingError("not_found_404")
    if code == 429:
        return GeminiProcessingError("quota")
    if code in _RETRYABLE_STATUS:
        return GeminiProcessingError(f"http_{code}")
    if code >= 400:
        return GeminiProcessingError(f"http_{code}")
    return GeminiProcessingError("api_error")


def _extract_output_text(interaction: Interaction) -> str:
    text = interaction.output_text
    if isinstance(text, str) and text.strip():
        return text.strip()
    if interaction.errors:
        logger.warning(
            "gemini_interaction_errors status=%s error_count=%s",
            interaction.status,
            len(interaction.errors),
        )
        raise GeminiProcessingError("interaction_failed")
    if interaction.status and str(interaction.status).lower() in {
        "failed",
        "incomplete",
    }:
        raise GeminiProcessingError("empty_response")
    raise GeminiProcessingError("empty_response")


def _create_interaction(client: genai.Client, *, model_id: str, prompt: str, stream: bool) -> Any:
    timeout = _gemini_timeout_seconds()
    log_ai_stage("gemini_interactions_create_start", model=model_id, timeout_s=timeout)
    started = time.perf_counter()
    try:
        interaction = client.interactions.create(
            model=model_id,
            input=prompt,
            stream=stream,
            timeout=timeout,
            automatic_continuation=False,
            generation_config=_INTERPRETATION_GENERATION_CONFIG,
        )
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        log_ai_stage("gemini_interactions_create_failed", elapsed_ms=f"{elapsed_ms:.1f}")
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    log_ai_stage("gemini_interactions_create_done", elapsed_ms=f"{elapsed_ms:.1f}")
    return interaction


class GenAiGeminiClient:
    """GenerationPort adapter using client.interactions.create()."""

    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client

    def _build_client(self) -> genai.Client:
        if self._client is not None:
            return self._client
        key = resolve_gemini_api_key()
        if not key:
            raise GeminiProcessingError("missing_api_key")
        return genai.Client(api_key=key, http_options=_gemini_http_options())

    def generate(self, prompt: str) -> str:
        # Hard wall-clock cap: the SDK may ignore HTTP timeouts on interactions.create().
        wall_limit = _gemini_timeout_seconds() + 5.0
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemini-call")
        future = pool.submit(self._generate_sync_inner, prompt)
        try:
            return future.result(timeout=wall_limit)
        except FuturesTimeoutError as exc:
            log_ai_stage("gemini_wall_clock_timeout", limit_s=wall_limit)
            raise GeminiProcessingError("timeout") from exc
        finally:
            # Do not wait on shutdown: a timed-out SDK call may never return.
            pool.shutdown(wait=False, cancel_futures=True)

    def _generate_sync_inner(self, prompt: str) -> str:
        if self._client is None:
            key = resolve_gemini_api_key()
            if not key:
                raise GeminiProcessingError("missing_api_key")
        model_id = _normalize_model_id(settings.API_GEMINI_MODEL)
        client = self._build_client()
        try:
            interaction = _create_interaction(
                client, model_id=model_id, prompt=prompt, stream=False
            )
            text = _extract_output_text(interaction)
            log_ai_stage("gemini_output_text_ok", chars=len(text))
            return text
        except GeminiProcessingError:
            raise
        except genai_errors.APIError as exc:
            mapped = _map_api_error(exc)
            log_ai_stage("gemini_api_error", reason=str(mapped))
            raise mapped from exc
        except httpx.TimeoutException as exc:
            log_ai_stage("gemini_http_timeout")
            raise GeminiProcessingError("timeout") from exc
        except httpx.HTTPError as exc:
            log_ai_stage("gemini_network_error")
            raise GeminiProcessingError("network") from exc
        except genai_errors.ClientError as exc:
            raise GeminiProcessingError("client_error") from exc
        except genai_errors.ServerError as exc:
            raise GeminiProcessingError("server_error") from exc

    def generate_stream(
        self,
        prompt: str,
        *,
        on_first_token: Callable[[], None] | None = None,
    ) -> Iterator[str]:
        """Stream text deltas (for future SSE); marks first token via callback."""
        key = resolve_gemini_api_key()
        if not key:
            raise GeminiProcessingError("missing_api_key")
        model_id = _normalize_model_id(settings.API_GEMINI_MODEL)
        client = self._build_client()
        first = False
        try:
            stream = _create_interaction(client, model_id=model_id, prompt=prompt, stream=True)
            for event in stream:
                if getattr(event, "event_type", None) == "content.delta":
                    delta = getattr(event, "delta", None)
                    text = getattr(delta, "text", None) if delta is not None else None
                    if text:
                        if not first:
                            first = True
                            if on_first_token:
                                on_first_token()
                        yield text
                interaction = getattr(event, "interaction", None)
                if interaction is not None and interaction.output_text and not first:
                    if on_first_token:
                        on_first_token()
                    yield interaction.output_text
                    return
        except genai_errors.APIError as exc:
            raise _map_api_error(exc) from exc


# Backward-compatible alias for wiring and tests migrating to the SDK client.
HttpGeminiClient = GenAiGeminiClient


def validate_gemini_text_generation(
    *,
    api_key: str | None = None,
    model: str | None = None,
    prompt: str = "Responde solo: ok",
) -> tuple[bool, str, int | None]:
    """
    Run one Interactions API call for diagnostics.
    Returns (ok, detail_message, http_status_or_none). Never includes secrets.
    """
    raw_key = (api_key or "").strip() or resolve_gemini_api_key()
    if not raw_key:
        return False, "missing_api_key", None

    model_id = _normalize_model_id(model or settings.API_GEMINI_MODEL)
    injected = genai.Client(api_key=raw_key, http_options=_gemini_http_options())
    try:
        started = time.perf_counter()
        text = GenAiGeminiClient(client=injected).generate(prompt)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("gemini_validate_ok model=%s latency_ms=%.1f", model_id, elapsed_ms)
        return True, text[:120], 200
    except GeminiProcessingError as exc:
        code = str(exc)
        status = None
        if code == "auth_401":
            status = 401
        elif code == "forbidden_403":
            status = 403
        elif code == "not_found_404":
            status = 404
        elif code == "quota":
            status = 429
        return False, code, status
    except genai_errors.APIError as exc:
        mapped = _map_api_error(exc)
        return False, str(mapped), getattr(exc, "code", None)
    except httpx.HTTPError:
        return False, "network", None
