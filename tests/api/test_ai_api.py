"""API tests for AI assistant endpoints (EP-10)."""

from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.main import app
from app.modules.ai.application.use_cases import (
    GeminiProcessingError,
    GenerateTextUseCase,
    ProcessVoiceUseCase,
)
from app.orchestration import ai_routes
from app.orchestration.ai_context import SqlAlchemyProjectContextBuilder
from tests.support import login_as


class StubTranscription:
    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        return "consulta de voz"


class StubGeneration:
    def generate(self, prompt: str) -> str:
        return "respuesta contextual"


class FailingGeneration:
    def generate(self, prompt: str) -> str:
        raise GeminiProcessingError("down")


class NoQuota:
    def check_and_consume(self, service: str) -> None:
        return None


def _voice_use_case(
    db: Session, generation: StubGeneration | FailingGeneration
) -> ProcessVoiceUseCase:
    from app.config import settings

    return ProcessVoiceUseCase(
        transcription=StubTranscription(),
        generation=generation,
        quotas=NoQuota(),
        project_context=SqlAlchemyProjectContextBuilder(db),
        min_bytes=settings.AI_VOICE_MIN_BYTES,
        max_bytes=settings.AI_VOICE_MAX_BYTES,
        max_seconds=float(settings.AI_VOICE_MAX_SECONDS),
    )


def test_text_generate_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/ai/text-generate", json={"text": "hola"})
    assert response.status_code == 401


def test_text_generate_success(client: TestClient, db_engine: Engine, db_session: Session) -> None:
    login_as(client, db_engine, email="dev@dashnode.local", role="developer")

    def override_text() -> GenerateTextUseCase:
        return GenerateTextUseCase(
            generation=StubGeneration(),
            quotas=NoQuota(),
            project_context=SqlAlchemyProjectContextBuilder(db_session),
        )

    app.dependency_overrides[ai_routes._text_use_case] = override_text
    response = client.post("/api/v1/ai/text-generate", json={"text": "Estado del sprint"})
    app.dependency_overrides.pop(ai_routes._text_use_case, None)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESPONDED"
    assert body["assistant_response"] == "respuesta contextual"


def test_voice_process_partial_gemini_failure(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    login_as(client, db_engine, email="dev2@dashnode.local", role="developer")

    def override_voice() -> ProcessVoiceUseCase:
        return _voice_use_case(db_session, FailingGeneration())

    app.dependency_overrides[ai_routes._voice_use_case] = override_voice
    files = {"audio": ("voice.webm", BytesIO(b"0" * 128), "audio/webm")}
    data = {"duration_seconds": "2"}
    response = client.post("/api/v1/ai/voice-process", files=files, data=data)
    app.dependency_overrides.pop(ai_routes._voice_use_case, None)
    assert response.status_code == 200
    body = response.json()
    assert body["recognized_text"] == "consulta de voz"
    assert body["assistant_response"] is None
    assert body["error"]
