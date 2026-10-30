"""Google Gemini text generation (official google-genai SDK, Interactions API)."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import httpx
from google import genai
from google.genai import errors as genai_errors

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError

if TYPE_CHECKING:
    from google.genai._gaos.types.interactions.interaction import Interaction

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
_GEMINI_TIMEOUT_SECONDS = 180.0
_RETRYABLE_STATUS = {502, 503, 504}


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
        return genai.Client(
            api_key=key,
            http_options={"timeout": int(_GEMINI_TIMEOUT_SECONDS * 1000)},
        )

    def generate(self, prompt: str) -> str:
        key = resolve_gemini_api_key()
        if not key:
            raise GeminiProcessingError("missing_api_key")
        model_id = _normalize_model_id(settings.API_GEMINI_MODEL)
        client = self._build_client()
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                interaction = client.interactions.create(
                    model=model_id,
                    input=prompt,
                    stream=False,
                    timeout=_GEMINI_TIMEOUT_SECONDS,
                )
                return _extract_output_text(interaction)
            except genai_errors.APIError as exc:
                mapped = _map_api_error(exc)
                if mapped.args[0] in {f"http_{s}" for s in _RETRYABLE_STATUS} and attempt == 0:
                    time.sleep(2.0)
                    last_exc = mapped
                    continue
                raise mapped from exc
            except httpx.TimeoutException as exc:
                raise GeminiProcessingError("timeout") from exc
            except httpx.HTTPError as exc:
                raise GeminiProcessingError("network") from exc
            except genai_errors.ClientError as exc:
                raise GeminiProcessingError("client_error") from exc
            except genai_errors.ServerError as exc:
                if attempt == 0:
                    time.sleep(2.0)
                    last_exc = exc
                    continue
                raise GeminiProcessingError("server_error") from exc
        if last_exc:
            raise last_exc
        raise GeminiProcessingError("unknown")


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
    client = genai.Client(
        api_key=raw_key,
        http_options={"timeout": 120_000},
    )
    try:
        interaction = client.interactions.create(
            model=model_id,
            input=prompt,
            stream=False,
            timeout=120.0,
        )
        text = _extract_output_text(interaction)
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
