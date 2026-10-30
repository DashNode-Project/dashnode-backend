"""Model selection, cooldown registry, and fallback for Gemini Interactions API."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import httpx
from google import genai
from google.genai import errors as genai_errors

from app.config import settings
from app.modules.ai.domain.errors import GeminiProcessingError
from app.modules.ai.infrastructure.gemini_client import (
    _create_interaction,
    _extract_output_text,
    _map_api_error,
    gemini_model_chain,
)
from app.shared.infrastructure.ai_request_trace import log_ai_stage

logger = logging.getLogger(__name__)

_PERMANENT_ERRORS = frozenset(
    {
        "missing_api_key",
        "auth_401",
        "forbidden_403",
    }
)
_FALLBACK_ERRORS = frozenset(
    {
        "not_found_404",
        "quota",
        "timeout",
        "network",
        "http_502",
        "http_503",
        "http_504",
        "interaction_failed",
        "empty_response",
        "server_error",
        "client_error",
        "api_error",
    }
)


@dataclass
class ModelRouteMetrics:
    model_id: str
    latency_ms: float
    attempt_index: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    http_code: int | None = None
    error_code: str | None = None


@dataclass
class _ModelState:
    cooldown_until: float = 0.0
    consecutive_failures: int = 0


class ModelAvailabilityRegistry:
    """In-memory cooldowns so exhausted/unavailable models are skipped temporarily."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, _ModelState] = {}

    def is_available(self, model_id: str, *, now: float | None = None) -> bool:
        ts = now if now is not None else time.time()
        with self._lock:
            state = self._states.get(model_id)
            if state is None:
                return True
            return ts >= state.cooldown_until

    def mark_success(self, model_id: str) -> None:
        with self._lock:
            self._states.pop(model_id, None)

    def mark_failure(self, model_id: str, error: GeminiProcessingError) -> None:
        code = str(error)
        if code in _PERMANENT_ERRORS:
            return
        cooldown = float(settings.AI_GEMINI_MODEL_COOLDOWN_SECONDS)
        with self._lock:
            state = self._states.setdefault(model_id, _ModelState())
            state.consecutive_failures += 1
            state.cooldown_until = time.time() + cooldown
        logger.info(
            "llm_model_cooldown model=%s reason=%s cooldown_s=%.0f failures=%s",
            model_id,
            code,
            cooldown,
            state.consecutive_failures,
        )


# Shared across requests within the process (worker lifetime).
_registry = ModelAvailabilityRegistry()


def _usage_tokens(interaction: object) -> tuple[int | None, int | None, int | None]:
    usage = getattr(interaction, "usage_metadata", None) or getattr(interaction, "usage", None)
    if usage is None:
        return None, None, None
    prompt = getattr(usage, "prompt_token_count", None) or getattr(usage, "input_tokens", None)
    output = getattr(usage, "candidates_token_count", None) or getattr(usage, "output_tokens", None)
    total = getattr(usage, "total_token_count", None) or getattr(usage, "total_tokens", None)
    return (
        int(prompt) if isinstance(prompt, int) else None,
        int(output) if isinstance(output, int) else None,
        int(total) if isinstance(total, int) else None,
    )


@dataclass
class LLMProviderRouter:
    """Selects an Interactions-compatible model and falls back on recoverable errors."""

    client: genai.Client
    registry: ModelAvailabilityRegistry | None = None

    def _registry(self) -> ModelAvailabilityRegistry:
        return self.registry if self.registry is not None else _registry
    model_chain: tuple[str, ...] | None = None

    def ordered_models(self) -> tuple[str, ...]:
        if self.model_chain is not None:
            return self.model_chain
        return gemini_model_chain()

    def generate(self, prompt: str) -> str:
        reg = self._registry()
        models = [m for m in self.ordered_models() if reg.is_available(m)]
        if not models:
            raise GeminiProcessingError("all_models_cooled_down")

        last_error: GeminiProcessingError | None = None
        metrics: list[ModelRouteMetrics] = []

        for attempt_index, model_id in enumerate(models):
            started = time.perf_counter()
            log_ai_stage("llm_router_attempt", model=model_id, attempt=attempt_index)
            try:
                interaction = _create_interaction(
                    self.client, model_id=model_id, prompt=prompt, stream=False
                )
                text = _extract_output_text(interaction)
                latency_ms = (time.perf_counter() - started) * 1000
                in_tok, out_tok, total_tok = _usage_tokens(interaction)
                reg.mark_success(model_id)
                metrics.append(
                    ModelRouteMetrics(
                        model_id=model_id,
                        latency_ms=latency_ms,
                        attempt_index=attempt_index,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        total_tokens=total_tok,
                    )
                )
                self._log_success(metrics[-1], models_skipped=attempt_index)
                log_ai_stage(
                    "llm_router_success",
                    model=model_id,
                    latency_ms=f"{latency_ms:.1f}",
                    attempts=attempt_index + 1,
                )
                return text
            except GeminiProcessingError as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                code = str(exc)
                metrics.append(
                    ModelRouteMetrics(
                        model_id=model_id,
                        latency_ms=latency_ms,
                        attempt_index=attempt_index,
                        error_code=code,
                    )
                )
                logger.warning(
                    "llm_router_model_failed model=%s latency_ms=%.1f error=%s attempt=%s",
                    model_id,
                    latency_ms,
                    code,
                    attempt_index,
                )
                if code in _PERMANENT_ERRORS:
                    raise
                last_error = exc
                reg.mark_failure(model_id, exc)
                if code not in _FALLBACK_ERRORS and not code.startswith("http_"):
                    raise
                continue
            except genai_errors.APIError as exc:
                mapped = _map_api_error(exc)
                latency_ms = (time.perf_counter() - started) * 1000
                code = str(mapped)
                if code in _PERMANENT_ERRORS:
                    raise mapped from exc
                last_error = mapped
                reg.mark_failure(model_id, mapped)
                logger.warning(
                    "llm_router_api_error model=%s http=%s latency_ms=%.1f",
                    model_id,
                    getattr(exc, "code", None),
                    latency_ms,
                )
                if code in _FALLBACK_ERRORS or code.startswith("http_"):
                    continue
                raise mapped from exc
            except httpx.HTTPError as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                if isinstance(exc, httpx.TimeoutException):
                    last_error = GeminiProcessingError("timeout")
                else:
                    last_error = GeminiProcessingError("network")
                reg.mark_failure(model_id, last_error)
                logger.warning(
                    "llm_router_transport_error model=%s latency_ms=%.1f error=%s",
                    model_id,
                    latency_ms,
                    str(last_error),
                )
                continue

        self._log_exhausted(metrics)
        if last_error is not None:
            raise last_error
        raise GeminiProcessingError("all_models_failed")

    def _log_success(self, metric: ModelRouteMetrics, *, models_skipped: int) -> None:
        logger.info(
            "llm_route_ok model=%s latency_ms=%.1f attempts=%s skipped=%s "
            "in_tokens=%s out_tokens=%s total_tokens=%s",
            metric.model_id,
            metric.latency_ms,
            metric.attempt_index + 1,
            models_skipped,
            metric.input_tokens,
            metric.output_tokens,
            metric.total_tokens,
        )

    def _log_exhausted(self, metrics: list[ModelRouteMetrics]) -> None:
        if not metrics:
            return
        logger.error(
            "llm_route_exhausted models=%s last_error=%s",
            ",".join(m.model_id for m in metrics),
            metrics[-1].error_code,
        )
