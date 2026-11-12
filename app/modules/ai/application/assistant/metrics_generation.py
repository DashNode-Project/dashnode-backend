"""Wrap GenerationPort to record Gemini latency in assistant metrics."""

from __future__ import annotations

from app.modules.ai.application.assistant.assistant_metrics import AssistantRequestMetrics
from app.modules.ai.domain.ports import GenerationPort


class MetricsGenerationPort:
    def __init__(self, inner: GenerationPort, metrics: AssistantRequestMetrics) -> None:
        self._inner = inner
        self._metrics = metrics

    def generate(self, prompt: str) -> str:
        self._metrics.start_gemini()
        try:
            return self._inner.generate(prompt)
        finally:
            self._metrics.stop_gemini()
