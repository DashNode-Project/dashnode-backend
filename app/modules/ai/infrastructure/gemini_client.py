"""Google Gemini text generation client (Gemini Developer API)."""

from __future__ import annotations

import time

import httpx

from app.config import settings
from app.modules.ai.application.use_cases import GeminiProcessingError

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


def _auth_headers(api_key: str) -> dict[str, str]:
    """Authenticate with Gemini Developer API (AI Studio keys use x-goog-api-key)."""
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }


def _normalize_model_id(model: str) -> str:
    name = model.strip()
    if name.startswith("models/"):
        name = name.removeprefix("models/")
    return name or DEFAULT_GEMINI_MODEL


def _raise_for_http_status(status_code: int) -> None:
    if status_code == 401:
        raise GeminiProcessingError("auth_401")
    if status_code == 403:
        raise GeminiProcessingError("forbidden_403")
    if status_code == 404:
        raise GeminiProcessingError("not_found_404")
    if status_code == 429:
        raise GeminiProcessingError("quota")
    if status_code >= 400:
        raise GeminiProcessingError(f"http_{status_code}")


def _generate_content_url(model_id: str) -> str:
    return f"{GEMINI_API_BASE}/models/{model_id}:generateContent"


def _parse_text_response(payload: dict) -> str:
    try:
        candidate = payload["candidates"][0]
        parts = candidate["content"]["parts"]
        texts = [part["text"] for part in parts if isinstance(part.get("text"), str)]
        finish = candidate.get("finishReason")
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiProcessingError("invalid_payload") from exc
    if not texts:
        if finish == "MAX_TOKENS":
            raise GeminiProcessingError("empty_response_max_tokens")
        raise GeminiProcessingError("empty_response")
    return "\n".join(texts)


class HttpGeminiClient:
    def generate(self, prompt: str) -> str:
        api_key = settings.API_GEMINI
        if api_key is None or not api_key.get_secret_value().strip():
            raise GeminiProcessingError("missing_api_key")
        key = api_key.get_secret_value().strip()
        model_id = _normalize_model_id(settings.API_GEMINI_MODEL)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 2048,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        headers = _auth_headers(key)
        url = _generate_content_url(model_id)
        timeout = httpx.Timeout(180.0, connect=20.0)
        retry_statuses = {502, 503, 504}
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=body)
                if response.status_code in retry_statuses:
                    time.sleep(2.0)
                    response = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise GeminiProcessingError("network") from exc
        if response.status_code >= 400:
            _raise_for_http_status(response.status_code)
        return _parse_text_response(response.json()).strip()


def validate_gemini_text_generation(
    *,
    api_key: str | None = None,
    model: str | None = None,
    prompt: str = "Responde solo: ok",
    client: httpx.Client | None = None,
) -> tuple[bool, str, int | None]:
    """
    Run one generateContent call for diagnostics.
    Returns (ok, detail_message, http_status_or_none). Never includes secrets.
    """
    raw_key = (api_key or "").strip()
    if not raw_key and settings.API_GEMINI is not None:
        raw_key = settings.API_GEMINI.get_secret_value().strip()
    if not raw_key:
        return False, "missing_api_key", None

    model_id = _normalize_model_id(model or settings.API_GEMINI_MODEL)
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = _auth_headers(raw_key)
    url = _generate_content_url(model_id)
    owns_client = client is None
    http = client or httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0))
    try:
        response = http.post(url, headers=headers, json=body)
        status = response.status_code
        if status == 401:
            return False, "auth_401", status
        if status == 403:
            return False, "forbidden_403", status
        if status == 404:
            return False, "not_found_404", status
        if status >= 400:
            return False, f"http_{status}", status
        text = _parse_text_response(response.json())
        return True, text[:120], status
    except GeminiProcessingError as exc:
        return False, str(exc), None
    except httpx.HTTPError:
        return False, "network", None
    finally:
        if owns_client:
            http.close()
