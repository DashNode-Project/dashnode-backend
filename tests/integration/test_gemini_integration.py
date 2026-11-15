"""Optional live Gemini Interactions API smoke test (skipped without API key)."""

from __future__ import annotations

import os

import pytest

from app.modules.ai.infrastructure.gemini_client import (
    GenAiGeminiClient,
    resolve_gemini_api_key,
    validate_gemini_text_generation,
)


def _live_gemini_enabled() -> bool:
    return os.environ.get("GEMINI_INTEGRATION", "").lower() in {"1", "true", "yes"}


@pytest.mark.skipif(
    not _live_gemini_enabled() or not resolve_gemini_api_key(),
    reason="Set GEMINI_INTEGRATION=1 and GEMINI_API_KEY/API_GEMINI to run live Gemini tests",
)
def test_live_interactions_generate() -> None:
    ok, detail, status = validate_gemini_text_generation(
        prompt="Responde en una palabra: confirmado"
    )
    if not ok and detail == "quota":
        pytest.skip("Gemini quota exhausted")
    assert ok is True, detail
    assert status == 200
    assert detail


@pytest.mark.skipif(
    not _live_gemini_enabled() or not resolve_gemini_api_key(),
    reason="Set GEMINI_INTEGRATION=1 and GEMINI_API_KEY/API_GEMINI to run live Gemini tests",
)
def test_live_client_output_text() -> None:
    client = GenAiGeminiClient()
    try:
        text = client.generate("Di solo: ok")
    except Exception as exc:
        if "quota" in str(exc).lower():
            pytest.skip("Gemini quota exhausted")
        raise
    assert text
    assert len(text) <= 200
