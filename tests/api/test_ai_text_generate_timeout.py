"""API tests for text-generate wall-clock timeout and concurrency (EP-10)."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.main import app
from app.modules.ai.application.dtos import AssistantResponseStatus, TextGenerateResponse
from app.modules.ai.application.use_cases import TextGenerateCommand
from app.orchestration import ai_routes
from tests.support import login_as


class _SlowTextUseCase:
    def __init__(self, delay_seconds: float) -> None:
        self._delay = delay_seconds

    def execute(self, cmd: TextGenerateCommand) -> TextGenerateResponse:
        time.sleep(self._delay)
        return TextGenerateResponse(
            recognized_text=cmd.text,
            assistant_response="late",
            status=AssistantResponseStatus.RESPONDED,
            error=None,
        )


class _FastDeterministicUseCase:
    def execute(self, cmd: TextGenerateCommand) -> TextGenerateResponse:
        return TextGenerateResponse(
            recognized_text=cmd.text,
            assistant_response="proyectos visibles",
            status=AssistantResponseStatus.RESPONDED,
            error=None,
        )


def test_text_generate_returns_ai_request_timeout(
    client: TestClient,
    db_engine: Engine,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login_as(client, db_engine, email="dev@dashnode.local", role="developer")
    monkeypatch.setattr(settings, "AI_TEXT_GENERATE_TIMEOUT_SECONDS", 0.05)

    app.dependency_overrides[ai_routes._text_use_case] = lambda: _SlowTextUseCase(delay_seconds=2.0)
    response = client.post("/api/v1/ai/text-generate", json={"text": "pregunta abierta xyz"})
    app.dependency_overrides.pop(ai_routes._text_use_case, None)

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "AI_REQUEST_TIMEOUT"


def test_text_generate_back_to_back_while_async_route(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    login_as(client, db_engine, email="dev@dashnode.local", role="developer")
    app.dependency_overrides[ai_routes._text_use_case] = lambda: _FastDeterministicUseCase()

    first = client.post("/api/v1/ai/text-generate", json={"text": "proyectos"})
    second = client.post("/api/v1/ai/text-generate", json={"text": "proyectos"})

    app.dependency_overrides.pop(ai_routes._text_use_case, None)
    assert first.status_code == 200
    assert second.status_code == 200
