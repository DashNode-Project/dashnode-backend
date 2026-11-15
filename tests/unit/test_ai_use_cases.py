"""Unit tests for AI voice/text use cases (HU 91, 93, 95)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.ai.application.use_cases import (
    GeminiProcessingError,
    ProcessVoiceUseCase,
    QuotaExhaustedError,
    VoiceProcessCommand,
    WhisperProcessingError,
)
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.assistant_data_queries import AssistantDataService
from app.shared.domain.errors import AppError


class FakeTranscription:
    def __init__(self, text: str = "cuales son mis proyectos") -> None:
        self.text = text

    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        return self.text


class FakeGeneration:
    def __init__(self, answer: str = "respuesta", fail: bool = False) -> None:
        self.answer = answer
        self.fail = fail

    def generate(self, prompt: str) -> str:
        if self.fail:
            raise GeminiProcessingError("fail")
        return self.answer


class FakeQuota:
    def check_and_consume(self, service: str) -> None:
        return None


class ExhaustedQuota:
    def check_and_consume(self, service: str) -> None:
        raise QuotaExhaustedError(service)


def _seed_project(db_session: Session, *, project_id: str = "p1", user_id: str = "u1") -> None:
    now = datetime.now(UTC)
    db_session.add(
        ProjectModel(
            id=project_id,
            name="DashNode Initial Project",
            description="",
            owner_id=user_id,
            manager_id=user_id,
            priority="media",
            tech_stack="[]",
            meeting_link=None,
            status="planificacion",
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        ProjectMemberModel(
            project_id=project_id,
            user_id=user_id,
            role="developer",
            joined_at=now,
        )
    )
    db_session.flush()


def _use_case(
    db_session: Session,
    transcription: FakeTranscription | None = None,
    generation: FakeGeneration | None = None,
    quotas: FakeQuota | ExhaustedQuota | None = None,
    *,
    transcription_override: object | None = None,
) -> ProcessVoiceUseCase:
    return ProcessVoiceUseCase(
        session=db_session,
        transcription=transcription_override or transcription or FakeTranscription(),  # type: ignore[arg-type]
        generation=generation or FakeGeneration(),
        quotas=quotas or FakeQuota(),
        data=AssistantDataService(db_session),
        min_bytes=10,
        max_bytes=100_000,
        max_seconds=60.0,
    )


def test_empty_audio_rejected(db_session: Session) -> None:
    uc = _use_case(db_session)
    with pytest.raises(AppError) as exc:
        uc.execute(
            VoiceProcessCommand(b"x", "audio/webm", None, None, "u1", "admin"),
        )
    assert exc.value.code == "EMPTY_AUDIO"


def test_voice_flow_list_projects(db_session: Session) -> None:
    _seed_project(db_session)
    result = _use_case(db_session).execute(
        VoiceProcessCommand(b"0" * 20, "audio/webm", 2.0, None, "u1", "admin"),
    )
    assert result.status == "RESPONDED"
    assert "DashNode Initial Project" in (result.assistant_response or "")


def test_partial_gemini_failure_still_responds(db_session: Session) -> None:
    _seed_project(db_session)
    result = _use_case(
        db_session,
        transcription=FakeTranscription("texto ambiguo xyz"),
        generation=FakeGeneration(fail=True),
    ).execute(
        VoiceProcessCommand(b"0" * 20, "audio/webm", 1.0, None, "u1", "admin"),
    )
    assert result.status == "RESPONDED"
    assert result.assistant_response


def test_quota_exhausted_maps_to_app_error(db_session: Session) -> None:
    uc = _use_case(db_session, quotas=ExhaustedQuota())
    with pytest.raises(AppError) as exc:
        uc.execute(
            VoiceProcessCommand(b"0" * 20, "audio/webm", 1.0, None, "u1", "admin"),
        )
    assert exc.value.code == "FREE_QUOTA_EXHAUSTED"


def test_whisper_failure_is_unavailable(db_session: Session) -> None:
    class FailWhisper:
        def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
            raise WhisperProcessingError("x")

    uc = _use_case(db_session, transcription_override=FailWhisper())
    with pytest.raises(AppError) as exc:
        uc.execute(
            VoiceProcessCommand(b"0" * 20, "audio/webm", 1.0, None, "u1", "admin"),
        )
    assert exc.value.code == "AI_PROCESSING_ERROR"
