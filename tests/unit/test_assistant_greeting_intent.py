"""Regression: greetings must not override functional assistant intents."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.intent_models import (
    ClarificationNeeded,
    IntentType,
    ParsedIntent,
)
from app.modules.ai.application.assistant.intent_parser import parse_intent
from app.modules.ai.application.assistant.orchestrator import AssistantOrchestrator
from app.modules.backlog.infrastructure.models import EpicModel, UserStoryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.assistant_data_queries import AssistantDataService

# Product docs use LIST_USER_STORIES; implementation enum is LIST_SPRINT_STORIES.
LIST_USER_STORIES = IntentType.LIST_SPRINT_STORIES


def _parse(text: str) -> ParsedIntent:
    return parse_intent(text, open_project_name=None, last_project_names=[])


@pytest.mark.parametrize(
    ("text", "expected_intent"),
    [
        ("Hola", IntentType.GREETING),
        ("Hola Gemini, ¿cómo vas?", IntentType.GREETING),
        ("Hola, asistente DashNode. ¿Cómo estás?", IntentType.GREETING),
        ("Hola, necesito ayuda", IntentType.GREETING),
        ("Buenos días", IntentType.GREETING),
        ("Hola, dime cuáles HUs tiene DashNode", LIST_USER_STORIES),
        ("Hola, dime cuáles HUs tiene Medifast", LIST_USER_STORIES),
        ("Hola, necesito saber las HUs de VozNotAI", LIST_USER_STORIES),
        ("¿Qué HUs tiene DashNode?", LIST_USER_STORIES),
        ("HUs de DashNode", LIST_USER_STORIES),
        ("Hola, ¿qué tareas pendientes tiene DashNode?", IntentType.LIST_TASKS),
        ("Buenos días, muéstrame los miembros de Medifast", IntentType.LIST_PROJECT_MEMBERS),
        ("Buenas tardes, resume el proyecto VozNotAI", IntentType.PROJECT_SUMMARY),
        ("Buenas tardes, ¿quiénes integran VozNotAI?", IntentType.LIST_PROJECT_MEMBERS),
        ("Hola, ¿qué HUs tiene DashNode?", LIST_USER_STORIES),
        ("Buenos días, resume Medifast", IntentType.PROJECT_SUMMARY),
    ],
)
def test_greeting_plus_functional_intent(text: str, expected_intent: IntentType) -> None:
    intent = _parse(text)
    assert intent.intent == expected_intent, text


def test_bare_hus_requests_project() -> None:
    intent = _parse("HUs")
    assert intent.intent == LIST_USER_STORIES
    assert intent.project_ref is None


def _seed_projects(db_session: Session) -> None:
    now = datetime.now(UTC)
    specs = (
        ("p1", "VozNotAI"),
        ("p2", "DashNode Initial Project"),
        ("p3", "Medifast"),
    )
    for pid, name in specs:
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
    db_session.add(
        EpicModel(
            id="e1",
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
            id="s1",
            epic_id="e1",
            project_id="p2",
            title="HU Tablero Kanban",
            user_role="Dev",
            reason="Ver flujo",
            acceptance_criteria="Columnas visibles",
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


class _NoGemini:
    def generate(self, prompt: str) -> str:
        raise AssertionError(f"unexpected Gemini call: {prompt[:80]!r}")


class _Quota:
    def check_and_consume(self, service: str) -> None:
        return None


def test_orchestrator_greeting_hus_dashnode_uses_db_not_gemini(db_session: Session) -> None:
    _seed_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Hola, dime cuáles HUs tiene DashNode", "u1", "admin", None)
    assert "HU Tablero Kanban" in answer
    assert "DashNode" in answer


def test_orchestrator_bare_hus_clarifies_project(db_session: Session) -> None:
    _seed_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    with pytest.raises(ClarificationNeeded):
        orch.answer("HUs", "u1", "admin", None)


def test_orchestrator_greeting_only_is_static_reply(db_session: Session) -> None:
    _seed_projects(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer("Hola", "u1", "admin", None)
    assert "asistente" in answer.lower()
