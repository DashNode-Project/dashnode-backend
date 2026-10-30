"""Google Gemini text generation (official google-genai SDK, Interactions API)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai.types import HttpOptionsDict

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError

if TYPE_CHECKING:
    from google.genai._gaos.types.interactions.interaction import Interaction

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
_GEMINI_TIMEOUT_SECONDS = 90.0
_RETRYABLE_STATUS = {502, 503, 504}
_INTERPRETATION_GENERATION_CONFIG: dict[str, object] = {
    "thinking_level": "low",
    "max_output_tokens": 512,
}
_GEMINI_HTTP_OPTIONS: HttpOptionsDict = {
    "timeout": int(_GEMINI_TIMEOUT_SECONDS * 1000),
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
    return client.interactions.create(
        model=model_id,
        input=prompt,
        stream=stream,
        timeout=_GEMINI_TIMEOUT_SECONDS,
        automatic_continuation=False,
        generation_config=_INTERPRETATION_GENERATION_CONFIG,
    )


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
        return genai.Client(api_key=key, http_options=_GEMINI_HTTP_OPTIONS)

    def generate(self, prompt: str) -> str:
        # Voice/text AI runs inside Starlette's thread pool (see ai_routes); avoid a nested
        # executor here — it deadlocked when all gemini-io workers waited on themselves.
        return self._generate_sync(prompt)

    def _generate_sync(self, prompt: str) -> str:
        key = resolve_gemini_api_key()
        if not key:
            raise GeminiProcessingError("missing_api_key")
        model_id = _normalize_model_id(settings.API_GEMINI_MODEL)
        client = self._build_client()
        try:
            interaction = _create_interaction(
                client, model_id=model_id, prompt=prompt, stream=False
            )
            return _extract_output_text(interaction)
        except genai_errors.APIError as exc:
            raise _map_api_error(exc) from exc
        except httpx.TimeoutException as exc:
            raise GeminiProcessingError("timeout") from exc
        except httpx.HTTPError as exc:
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
    client = genai.Client(api_key=raw_key, http_options=_GEMINI_HTTP_OPTIONS)
    try:
        started = time.perf_counter()
        interaction = _create_interaction(client, model_id=model_id, prompt=prompt, stream=False)
        elapsed_ms = (time.perf_counter() - started) * 1000
        text = _extract_output_text(interaction)
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
