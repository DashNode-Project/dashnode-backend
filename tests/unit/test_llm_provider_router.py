"""Unit tests for LLMProviderRouter (model chain, fallback, cooldown)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors as genai_errors

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError
from app.modules.ai.infrastructure import gemini_client as gc
from app.modules.ai.infrastructure.llm_provider_router import (
    LLMProviderRouter,
    ModelAvailabilityRegistry,
)


def _ok_interaction(text: str = "ok") -> MagicMock:
    interaction = MagicMock()
    interaction.output_text = text
    interaction.errors = None
    interaction.status = "completed"
    interaction.usage_metadata = MagicMock(
        prompt_token_count=10, candidates_token_count=5, total_token_count=15
    )
    return interaction


def test_gemini_model_chain_dedupes_primary_and_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "API_GEMINI_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setattr(
        settings,
        "AI_GEMINI_FALLBACK_MODELS",
        "gemini-3.1-flash-lite,gemini-3.8-flash",
    )
    assert gc.gemini_model_chain() == (
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    )


def test_router_fallback_on_not_found_404() -> None:
    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = [
        genai_errors.APIError(404, {"error": {"message": "model not found"}}, None),
        _ok_interaction("from-fallback"),
    ]
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions
    registry = ModelAvailabilityRegistry()

    router = LLMProviderRouter(
        client=mock_client,
        registry=registry,
        model_chain=("model-a", "model-b"),
    )
    assert router.generate("hello") == "from-fallback"
    assert mock_interactions.create.call_count == 2
    assert mock_interactions.create.call_args_list[0].kwargs["model"] == "model-a"
    assert mock_interactions.create.call_args_list[1].kwargs["model"] == "model-b"


def test_router_auth_401_does_not_fallback() -> None:
    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = genai_errors.APIError(
        401, {"error": {"message": "unauthenticated"}}, None
    )
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions
    registry = ModelAvailabilityRegistry()

    router = LLMProviderRouter(
        client=mock_client,
        registry=registry,
        model_chain=("model-a", "model-b"),
    )
    with pytest.raises(GeminiProcessingError, match="auth_401"):
        router.generate("hello")
    mock_interactions.create.assert_called_once()


def test_router_skips_model_in_cooldown() -> None:
    mock_interactions = MagicMock()
    mock_interactions.create.return_value = _ok_interaction("only-b")
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions
    registry = ModelAvailabilityRegistry()
    registry.mark_failure("model-a", GeminiProcessingError("quota"))

    router = LLMProviderRouter(
        client=mock_client,
        registry=registry,
        model_chain=("model-a", "model-b"),
    )
    assert router.generate("ping") == "only-b"
    mock_interactions.create.assert_called_once()
    assert mock_interactions.create.call_args.kwargs["model"] == "model-b"


def test_router_all_models_cooled_down_raises() -> None:
    registry = ModelAvailabilityRegistry()
    registry.mark_failure("model-a", GeminiProcessingError("quota"))
    registry.mark_failure("model-b", GeminiProcessingError("quota"))
    mock_client = MagicMock()

    router = LLMProviderRouter(
        client=mock_client,
        registry=registry,
        model_chain=("model-a", "model-b"),
    )
    with pytest.raises(GeminiProcessingError, match="all_models_cooled_down"):
        router.generate("x")
    mock_client.interactions.create.assert_not_called()


def test_router_timeout_then_success() -> None:
    mock_interactions = MagicMock()
    mock_interactions.create.side_effect = [
        httpx.TimeoutException("slow"),
        _ok_interaction("recovered"),
    ]
    mock_client = MagicMock()
    mock_client.interactions = mock_interactions
    registry = ModelAvailabilityRegistry()

    router = LLMProviderRouter(
        client=mock_client,
        registry=registry,
        model_chain=("fast-fail", "fast-ok"),
    )
    assert router.generate("q") == "recovered"
    assert mock_interactions.create.call_count == 2
