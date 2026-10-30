"""Unit tests for Gemini SDK client (Interactions API, auth, errors)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google import genai
from google.genai import errors as genai_errors

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError
from app.modules.ai.infrastructure import gemini_client as gc
from app.modules.ai.infrastructure.gemini_client import GenAiGeminiClient


def test_normalize_model_id_strips_prefix_and_default() -> None:
    assert gc._normalize_model_id("models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert gc._normalize_model_id("  gemini-3.8-flash  ") == "gemini-3.8-flash"
    assert gc._normalize_model_id("") == gc.DEFAULT_GEMINI_MODEL
    assert gc.DEFAULT_GEMINI_MODEL == "gemini-3.1-flash-lite"


def test_resolve_gemini_api_key_prefers_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "GEMINI_API_KEY",
        type("S", (), {"get_secret_value": lambda self: "GEMINI_KEY"})(),
    )
    monkeypatch.setattr(
        settings,
        "API_GEMINI",
        type("S", (), {"get_secret_value": lambda self: "LEGACY"})(),
    )
    assert gc.resolve_gemini_api_key() == "GEMINI_KEY"


def test_generate_success_via_interactions(monkeypatch: pytest.MonkeyPatch) -> None:
    interaction = MagicMock()
    interaction.output_text = "Hola"
    interaction.errors = None
    interaction.status = "completed"

    mock_interactions = MagicMock()
    mock_interactions.create.return_value = interaction
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: "AQ.test")
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    client = GenAiGeminiClient(client=mock_client)
    assert client.generate("ping") == "Hola"
    mock_interactions.create.assert_called_once()
    kwargs = mock_interactions.create.call_args.kwargs
    assert kwargs["model"] == "gemini-3.8-flash"
    assert kwargs["input"] == "ping"
    assert kwargs["stream"] is False


@pytest.mark.parametrize(
    ("status_code", "code"),
    [
        (401, "auth_401"),
        (403, "forbidden_403"),
        (404, "not_found_404"),
        (429, "quota"),
        (503, "http_503"),
    ],
)
def test_generate_maps_api_errors(
    monkeypatch: pytest.MonkeyPatch, status_code: int, code: str
) -> None:
    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = genai_errors.APIError(
        status_code, {"error": {"message": "fail"}}, None
    )
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: "AQ.test")
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    with pytest.raises(GeminiProcessingError, match=code):
        GenAiGeminiClient(client=mock_client).generate("ping")


def test_generate_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: None)
    with pytest.raises(GeminiProcessingError, match="missing_api_key"):
        GenAiGeminiClient().generate("ping")


def test_validate_gemini_text_generation_ok() -> None:
    interaction = MagicMock()
    interaction.output_text = "ok"
    interaction.errors = None
    interaction.status = "completed"

    mock_interactions = MagicMock()
    mock_interactions.create.return_value = interaction
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    with patch.object(genai, "Client", return_value=mock_client):
        ok, detail, status = gc.validate_gemini_text_generation(
            api_key="AQ.test", model="gemini-3.8-flash"
        )
    assert ok is True
    assert detail == "ok"
    assert status == 200


def test_generate_empty_output_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    interaction = MagicMock()
    interaction.output_text = "   "
    interaction.errors = None
    interaction.status = "completed"

    mock_interactions = MagicMock()
    mock_interactions.create.return_value = interaction
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: "AQ.test")
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    with pytest.raises(GeminiProcessingError, match="empty_response"):
        GenAiGeminiClient(client=mock_client).generate("ping")


def test_generate_maps_httpx_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = httpx.TimeoutException("timed out")
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: "AQ.test")
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    with pytest.raises(GeminiProcessingError, match="timeout"):
        GenAiGeminiClient(client=mock_client).generate("ping")


def test_generate_wall_clock_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def _slow_create(**kwargs: object) -> MagicMock:
        time.sleep(8)
        interaction = MagicMock()
        interaction.output_text = "late"
        interaction.errors = None
        interaction.status = "completed"
        return interaction

    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = _slow_create
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: "AQ.test")
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "AI_GEMINI_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(GeminiProcessingError, match="timeout"):
        GenAiGeminiClient(client=mock_client).generate("ping")


def test_generate_maps_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = httpx.ConnectError("connection refused")
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    monkeypatch.setattr(gc, "resolve_gemini_api_key", lambda: "AQ.test")
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.8-flash")

    with pytest.raises(GeminiProcessingError, match="network"):
        GenAiGeminiClient(client=mock_client).generate("ping")


def test_validate_gemini_text_generation_auth_401() -> None:
    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = genai_errors.APIError(
        401, {"error": {"message": "unauthenticated"}}, None
    )
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions

    with patch.object(genai, "Client", return_value=mock_client):
        ok, detail, status = gc.validate_gemini_text_generation(
            api_key="AQ.bad", model="gemini-3.8-flash"
        )
    assert ok is False
    assert detail == "auth_401"
    assert status == 401
