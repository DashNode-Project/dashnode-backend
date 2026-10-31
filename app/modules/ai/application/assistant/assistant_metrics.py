"""Structured latency metrics for the hybrid assistant pipeline."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AssistantRequestMetrics:
    intent_parse_ms: float = 0.0
    entity_resolve_ms: float = 0.0
    postgres_ms: float = 0.0
    gemini_ms: float = 0.0
    gemini_calls: int = 0
    gemini_first_token_ms: float | None = None
    orchestrator_ms: float = 0.0
    total_ms: float = 0.0
    path: str = "unknown"
    _postgres_started: float | None = field(default=None, repr=False)
    _gemini_started: float | None = field(default=None, repr=False)

    def start_postgres(self) -> None:
        self._postgres_started = time.perf_counter()

    def stop_postgres(self) -> None:
        if self._postgres_started is not None:
            self.postgres_ms += (time.perf_counter() - self._postgres_started) * 1000
            self._postgres_started = None

    def start_gemini(self) -> None:
        self._gemini_started = time.perf_counter()
        self.gemini_calls += 1

    def mark_gemini_first_token(self) -> None:
        if self._gemini_started is not None and self.gemini_first_token_ms is None:
            self.gemini_first_token_ms = (time.perf_counter() - self._gemini_started) * 1000

    def stop_gemini(self) -> None:
        if self._gemini_started is not None:
            self.gemini_ms += (time.perf_counter() - self._gemini_started) * 1000
            self._gemini_started = None

    def log(self, *, user_id: str) -> None:
        logger.info(
            "assistant_request_metrics user_id=%s path=%s total_ms=%.1f "
            "parse_ms=%.1f resolve_ms=%.1f postgres_ms=%.1f gemini_ms=%.1f "
            "gemini_calls=%s gemini_ttft_ms=%s orchestrator_ms=%.1f",
            user_id,
            self.path,
            self.total_ms,
            self.intent_parse_ms,
            self.entity_resolve_ms,
            self.postgres_ms,
            self.gemini_ms,
            self.gemini_calls,
            f"{self.gemini_first_token_ms:.1f}" if self.gemini_first_token_ms else "-",
            self.orchestrator_ms,
        )
