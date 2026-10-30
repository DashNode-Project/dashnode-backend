"""Regression tests for reported assistant query failures."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.intent_models import ClarificationNeeded, IntentType
from app.modules.ai.application.assistant.intent_parser import parse_intent
from app.modules.ai.application.assistant.orchestrator import AssistantOrchestrator
from app.modules.backlog.infrastructure.models import EpicModel, UserStoryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.assistant_data_queries import AssistantDataService


class _Quota:
    def check_and_consume(self, service: str) -> None:
        return None


def _seed_projects(db_session: Session, user_id: str = "u1") -> None:
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


def _seed_voznotai_story(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        EpicModel(
            id="e1",
            project_id="p1",
            name="Core",
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
            id="s1",
            epic_id="e1",
            project_id="p1",
            title="HU Autenticación por voz",
            user_role="Usuario",
            reason="Iniciar sesión",
            acceptance_criteria="Debe validar credenciales",
            moscow_priority="must_have",
            story_points=5,
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


def test_parser_global_members_each_project() -> None:
    intent = parse_intent(
        "Dime qué miembros hay en cada proyecto",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.LIST_ALL_PROJECT_MEMBERS


def test_parser_analyze_hus_ambiguous_without_project() -> None:
    intent = parse_intent(
        "Dime qué mejorar en las HUs",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.ANALYZE_USER_STORIES
    assert intent.project_ref is None


def test_parser_analyze_hus_extracts_dashnode_ref() -> None:
    intent = parse_intent(
        "Dime qué mejorar en las HUs de DashNode",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.ANALYZE_USER_STORIES
    assert intent.project_ref is not None
    assert "dashnode" in intent.project_ref.lower()


def test_parser_gemini_grounded_voznotai() -> None:
    intent = parse_intent(
        "Pregúntale a Gemini qué HUs hay en VozNotAI",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.GEMINI_GROUNDED


class _NoGemini:
    def generate(self, prompt: str) -> str:
        raise AssertionError("unexpected gemini")


def test_orchestrator_global_members(db_session: Session) -> None:
    _seed_projects(db_session)

    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Dime qué miembros hay en cada proyecto", "u1", "admin", None)
    assert "VozNotAI" in answer
    assert "DashNode" in answer
    assert "Miembros por proyecto" in answer


def test_orchestrator_analyze_hus_needs_project_when_many(db_session: Session) -> None:
    _seed_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    with pytest.raises(ClarificationNeeded, match="recomendaciones"):
        orch.answer("Dime qué mejorar en las HUs", "u1", "admin", None)


def test_orchestrator_analyze_hus_dashnode_uses_gemini_with_context(db_session: Session) -> None:
    _seed_projects(db_session)
    _seed_voznotai_story(db_session)
    now = datetime.now(UTC)
    db_session.add(
        EpicModel(
            id="e2",
            project_id="p2",
            name="Core",
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
            id="s2",
            epic_id="e2",
            project_id="p2",
            title="HU Tablero",
            user_role="Dev",
            reason="Ver kanban",
            acceptance_criteria="Columnas visibles",
            moscow_priority="must_have",
            story_points=3,
            estimation_mode="story",
            sprint_id=None,
            sort_order=0,
            created_by="u1",
            created_at=now,
            updated_at=now,
            label="HU-02",
        )
    )
    db_session.flush()
    captured: list[str] = []

    class _Gemini:
        def generate(self, prompt: str) -> str:
            captured.append(prompt)
            return "Revise criterios de aceptación."

    orch = AssistantOrchestrator(db_session, _Gemini(), _Quota(), AssistantDataService(db_session))
    answer = orch.answer("Dime qué mejorar en las HUs de DashNode", "u1", "admin", None)
    assert "Revise" in answer
    assert captured
    assert "DashNode Initial Project" in captured[0]
    assert "Criterios de aceptación" in captured[0]


def test_orchestrator_list_hus_voznotai_from_db(db_session: Session) -> None:
    _seed_projects(db_session)
    _seed_voznotai_story(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Lista las HUs de VozNotAI", "u1", "admin", None)
    assert "HU Autenticación por voz" in answer
    assert "No hay historias" not in answer


def test_orchestrator_gemini_grounded_includes_story_titles(db_session: Session) -> None:
    _seed_projects(db_session)
    _seed_voznotai_story(db_session)
    captured: list[str] = []

    class _Gemini:
        def generate(self, prompt: str) -> str:
            captured.append(prompt)
            return "Hay 1 HU: autenticación por voz."

    orch = AssistantOrchestrator(db_session, _Gemini(), _Quota(), AssistantDataService(db_session))
    answer = orch.answer("Pregúntale a Gemini qué HUs hay en VozNotAI", "u1", "admin", None)
    assert "autenticación" in answer.lower()
    assert captured
    assert "HU Autenticación por voz" in captured[0]
