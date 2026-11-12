"""Unit tests for assistant orchestrator (intent routing without Gemini)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.intent_models import ClarificationNeeded
from app.modules.ai.application.assistant.orchestrator import AssistantOrchestrator
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.assistant_data_queries import AssistantDataService


class _NoGemini:
    def generate(self, prompt: str) -> str:
        raise AssertionError("Gemini should not be called")


class _Quota:
    def check_and_consume(self, service: str) -> None:
        return None


def _seed_two_projects(db_session: Session, user_id: str = "u1") -> None:
    now = datetime.now(UTC)
    for pid, name in (("p1", "VozNotAI"), ("p2", "DashNode Initial Project")):
        db_session.add(
            ProjectModel(
                id=pid,
                name=name,
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
                project_id=pid,
                user_id=user_id,
                role="developer",
                joined_at=now,
            )
        )
    db_session.flush()


def test_list_projects_short_phrase(db_session: Session) -> None:
    _seed_two_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    for text in ("proyectos", "que proyectos", "proyectos disponibles"):
        answer = orch.answer(text, "u1", "admin", None)
        assert "VozNotAI" in answer
        assert "DashNode Initial Project" in answer


def test_count_hus_resolves_embedded_project(db_session: Session) -> None:
    _seed_two_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Cuántas HUs tiene VozNotAI", "u1", "admin", None)
    assert "VozNotAI" in answer
    assert "historia" in answer.lower()


def test_bare_project_name_focus(db_session: Session) -> None:
    _seed_two_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("VozNotAI", "u1", "admin", None)
    assert "VozNotAI" in answer
    assert "HUs" in answer


def test_pending_in_dashnode_resolves(db_session: Session) -> None:
    _seed_two_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Qué tengo pendiente en DashNode", "u1", "admin", None)
    assert "DashNode" in answer or "tareas" in answer.lower()


def test_unknown_gemini_quota_raises(db_session: Session) -> None:
    from app.modules.ai.domain.errors import GeminiProcessingError, QuotaExhaustedError

    _seed_two_projects(db_session)

    class _FailGemini:
        def generate(self, prompt: str) -> str:
            raise GeminiProcessingError("quota")

    orch = AssistantOrchestrator(
        db_session, _FailGemini(), _Quota(), AssistantDataService(db_session)
    )
    with pytest.raises(QuotaExhaustedError):
        orch.answer("texto ambiguo xyz", "u1", "admin", None)


def test_unknown_gemini_generic_error_returns_message(db_session: Session) -> None:
    from app.modules.ai.domain.errors import GeminiProcessingError

    _seed_two_projects(db_session)

    class _FailGemini:
        def generate(self, prompt: str) -> str:
            raise GeminiProcessingError("network")

    orch = AssistantOrchestrator(
        db_session, _FailGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("texto ambiguo xyz", "u1", "admin", None)
    assert "No pude procesar" in answer


def test_unknown_gemini_timeout_returns_message(db_session: Session) -> None:
    from app.modules.ai.domain.errors import GeminiProcessingError

    _seed_two_projects(db_session)

    class _SlowGemini:
        def generate(self, prompt: str) -> str:
            raise GeminiProcessingError("timeout")

    orch = AssistantOrchestrator(
        db_session, _SlowGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("texto ambiguo xyz", "u1", "admin", None)
    assert "tardó demasiado" in answer.lower()


def test_stories_voice_phrase_needs_existing_project(db_session: Session) -> None:
    _seed_two_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    with pytest.raises(ClarificationNeeded):
        orch.answer("Historias de usuario tiene mi proyecto BOSS ahí", "u1", "admin", None)
