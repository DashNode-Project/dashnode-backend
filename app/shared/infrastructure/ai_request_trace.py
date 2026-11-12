"""Correlated logging stages for AI assistant HTTP requests (EP-10)."""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from typing import Any

logger = logging.getLogger("dashnode.ai.request")

_request_id: ContextVar[str | None] = ContextVar("ai_request_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def current_request_id() -> str:
    return _request_id.get() or "-"


def log_ai_stage(stage: str, **fields: Any) -> None:
    if not fields:
        logger.info("ai_request request_id=%s stage=%s", current_request_id(), stage)
        return
    parts = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("ai_request request_id=%s stage=%s %s", current_request_id(), stage, parts)
