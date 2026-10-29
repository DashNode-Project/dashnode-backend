"""Unit tests for Gemini Developer API client (auth, model config, HTTP errors)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from app.modules.ai.application.use_cases import GeminiProcessingError
from app.modules.ai.infrastructure import gemini_client as gc
from app.modules.ai.infrastructure.gemini_client import HttpGeminiClient


def test_auth_headers_use_x_goog_api_key_not_bearer() -> None:
    for key in ("AQ.AbCdEf", "AIzaSyExample", "plain-key"):
        headers = gc._auth_headers(key)
        assert headers["x-goog-api-key"] == key
        assert "Authorization" not in headers


def test_normalize_model_id_strips_prefix_and_default() -> None:
    assert gc._normalize_model_id("models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert gc._normalize_model_id("  gemini-3.8-flash  ") == "gemini-3.8-flash"
    assert gc._normalize_model_id("") == gc.DEFAULT_GEMINI_MODEL


def test_raise_for_http_status_distinct_codes() -> None:
    with pytest.raises(GeminiProcessingError, match="auth_401"):
        gc._raise_for_http_status(401)
    with pytest.raises(GeminiProcessingError, match="forbidden_403"):
        gc._raise_for_http_status(403)
    with pytest.raises(GeminiProcessingError, match="not_found_404"):
        gc._raise_for_http_status(404)
    with pytest.raises(GeminiProcessingError, match="quota"):
        gc._raise_for_http_status(429)


def test_generate_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Hola"}]}, "finishReason": "STOP"},
        ],
    }

    mock_http = MagicMock()
    mock_http.post.return_value = mock_response
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(gc.httpx, "Client", lambda **_: mock_http)
    monkeypatch.setattr(
        gc.settings,
        "API_GEMINI",
        type("S", (), {"get_secret_value": lambda self: "AQ.test"})(),
    )
    monkeypatch.setattr(gc.settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    assert HttpGeminiClient().generate("ping") == "Hola"
    call_kwargs = mock_http.post.call_args
    assert call_kwargs.kwargs["headers"]["x-goog-api-key"] == "AQ.test"
    assert "Bearer" not in str(call_kwargs.kwargs["headers"])
    assert "gemini-3.8-flash:generateContent" in call_kwargs.args[0]


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "auth_401"), (403, "forbidden_403"), (404, "not_found_404")],
)
def test_generate_maps_http_errors(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = status

    mock_http = MagicMock()
    mock_http.post.return_value = mock_response
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(gc.httpx, "Client", lambda **_: mock_http)
    monkeypatch.setattr(
        gc.settings,
        "API_GEMINI",
        type("S", (), {"get_secret_value": lambda self: "AQ.test"})(),
    )
    monkeypatch.setattr(gc.settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    with pytest.raises(GeminiProcessingError, match=code):
        HttpGeminiClient().generate("ping")


def test_validate_gemini_text_generation_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-goog-api-key") == "AQ.test"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    ok, detail, status = gc.validate_gemini_text_generation(
        api_key="AQ.test", model="gemini-3.8-flash", client=client
    )
    assert ok is True
    assert detail == "ok"
    assert status == 200


def test_validate_gemini_text_generation_auth_401() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(401, json={"error": {"message": "unauthenticated"}})
    )
    client = httpx.Client(transport=transport)
    ok, detail, status = gc.validate_gemini_text_generation(
        api_key="AQ.bad", model="gemini-3.8-flash", client=client
    )
    assert ok is False
    assert detail == "auth_401"
    assert status == 401
