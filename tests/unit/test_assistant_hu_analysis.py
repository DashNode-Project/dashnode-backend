"""HU analysis / review intent, context, and error handling."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.intent_models import ClarificationNeeded, IntentType
from app.modules.ai.application.assistant.intent_parser import parse_intent
from app.modules.ai.application.assistant.orchestrator import AssistantOrchestrator
from app.modules.ai.domain.errors import GeminiProcessingError
from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.infrastructure.models import EpicModel, UserStoryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.assistant_data_queries import AssistantDataService

MEDIFAST_QUERY = "Hola, necesito saber si las HUs de mi proyecto Medifast están bien redactadas"


class _Quota:
    def check_and_consume(self, service: str) -> None:
        return None


def _seed_medifast_with_story(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        ProjectModel(
            id="p-med",
            name="Medifast",
            description="Nutrición",
            owner_id="u1",
            manager_id="u1",
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
            project_id="p-med",
            user_id="u1",
            role="developer",
            joined_at=now,
        )
    )
    db_session.add(
        EpicModel(
            id="e-med",
            project_id="p-med",
            name="App",
            description="",
            color=None,
            sort_order=0,
            created_by="u1",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        UserStoryModel(
            id="s-med",
            epic_id="e-med",
            project_id="p-med",
            title="Registrar comida",
            user_role="Usuario",
            reason="Llevar dieta",
            acceptance_criteria="Debe guardar calorías y mostrar resumen diario",
            moscow_priority="must_have",
            story_points=3,
            estimation_mode="story",
            sprint_id=None,
            sort_order=0,
            created_by="u1",
            created_at=now,
            updated_at=now,
            label="HU-01",
        )
    )
    db_session.flush()


def test_manager_can_query_project_without_membership_row(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        UserModel(
            id="mgr-only",
            email="mgr-only@test.local",
            name="Manager Solo",
            role="manager",
            hashed_password="x",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        ProjectModel(
            id="legacy-medifast",
            name="Medifast",
            description="Proyecto legado",
            owner_id="owner-x",
            manager_id="mgr-only",
            priority="media",
            tech_stack="[]",
            meeting_link=None,
            status="planificacion",
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()

    class _NoGemini:
        def generate(self, prompt: str) -> str:
            raise AssertionError("Gemini should not be called")

    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Cuántas HUs tiene Medifast", "mgr-only", "manager", None)
    assert "permiso" not in answer.lower()
    assert "Medifast" in answer


def test_medifast_redaction_query_classifies_as_analyze() -> None:
    intent = parse_intent(MEDIFAST_QUERY, open_project_name=None, last_project_names=[])
    assert intent.intent == IntentType.REVIEW_USER_STORIES
    assert intent.project_ref is not None
    assert "medifast" in intent.project_ref.lower()


def test_orchestrator_medifast_analysis_uses_gemini_with_story_detail(
    db_session: Session,
) -> None:
    _seed_medifast_with_story(db_session)
    captured: list[str] = []

    class _Gemini:
        def generate(self, prompt: str) -> str:
            captured.append(prompt)
            return "Las HUs son claras; sugiero acortar criterios."

    orch = AssistantOrchestrator(db_session, _Gemini(), _Quota(), AssistantDataService(db_session))
    answer = orch.answer(MEDIFAST_QUERY, "u1", "admin", None)
    assert "claras" in answer.lower() or "sugiero" in answer.lower()
    assert captured
    assert "Registrar comida" in captured[0]
    assert "Criterios de aceptación" in captured[0]
    assert "asistente de DashNode" in captured[0]


def test_orchestrator_medifast_no_stories_informs_without_gemini(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        ProjectModel(
            id="p-empty",
            name="Medifast",
            description="",
            owner_id="u1",
            manager_id="u1",
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
            project_id="p-empty",
            user_id="u1",
            role="developer",
            joined_at=now,
        )
    )
    db_session.flush()

    class _Gemini:
        def generate(self, prompt: str) -> str:
            raise AssertionError("Gemini must not run when there are zero HUs")

    orch = AssistantOrchestrator(db_session, _Gemini(), _Quota(), AssistantDataService(db_session))
    answer = orch.answer(MEDIFAST_QUERY, "u1", "admin", None)
    assert "No hay historias" in answer


def test_orchestrator_gemini_all_models_failed_message(db_session: Session) -> None:
    _seed_medifast_with_story(db_session)

    class _FailGemini:
        def generate(self, prompt: str) -> str:
            raise GeminiProcessingError("all_models_failed")

    orch = AssistantOrchestrator(
        db_session, _FailGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer(MEDIFAST_QUERY, "u1", "admin", None)
    assert "DashNode" in answer
    assert "modelos" in answer.lower()


def test_orchestrator_db_error_returns_recovery_message(db_session: Session) -> None:
    _seed_medifast_with_story(db_session)
    data = AssistantDataService(db_session)
    original = data.accessible_projects

    def _boom(user_id: str, role: str) -> list[object]:
        raise SQLAlchemyError("db down")

    data.accessible_projects = _boom  # type: ignore[method-assign, assignment]

    orch = AssistantOrchestrator(db_session, MagicMock(), _Quota(), data)
    answer = orch.answer(MEDIFAST_QUERY, "u1", "admin", None)
    assert "recuperar" in answer.lower()
    data.accessible_projects = original  # type: ignore[method-assign]


def test_voznotai_improvement_query(db_session: Session) -> None:
    now = datetime.now(UTC)
    for pid, name in (("p1", "VozNotAI"), ("p2", "Otro")):
        db_session.add(
            ProjectModel(
                id=pid,
                name=name,
                description="",
                owner_id="u1",
                manager_id="u1",
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
                user_id="u1",
                role="developer",
                joined_at=now,
            )
        )
    db_session.flush()
    intent = parse_intent(
        "¿Qué mejorarías en las HUs de VozNotAI?",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.IMPROVE_USER_STORIES


def test_ambiguous_analysis_requests_clarification(db_session: Session) -> None:
    now = datetime.now(UTC)
    for pid, name in (("p1", "Alpha"), ("p2", "Beta")):
        db_session.add(
            ProjectModel(
                id=pid,
                name=name,
                description="",
                owner_id="u1",
                manager_id="u1",
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
                user_id="u1",
                role="developer",
                joined_at=now,
            )
        )
    db_session.flush()
    orch = AssistantOrchestrator(
        db_session, MagicMock(), _Quota(), AssistantDataService(db_session)
    )
    with pytest.raises(ClarificationNeeded):
        orch.answer("¿Qué mejorar en las HUs?", "u1", "admin", None)
