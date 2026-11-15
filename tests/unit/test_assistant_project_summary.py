"""Project summary intent and orchestrator (deterministic, no Gemini)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.intent_models import IntentType
from app.modules.ai.application.assistant.intent_parser import parse_intent
from app.modules.ai.application.assistant.orchestrator import AssistantOrchestrator
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.assistant_data_queries import AssistantDataService


class _NoGemini:
    def generate(self, prompt: str) -> str:
        raise AssertionError("Gemini must not be called for project summary")


class _Quota:
    def check_and_consume(self, service: str) -> None:
        return None


def _seed_dashnode_project(db_session: Session, user_id: str = "u1") -> None:
    now = datetime.now(UTC)
    db_session.add(
        ProjectModel(
            id="p-dash",
            name="DashNode Initial Project",
            description="Plataforma de gestión ágil",
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
            project_id="p-dash",
            user_id=user_id,
            role="developer",
            joined_at=now,
        )
    )
    db_session.flush()


@pytest.mark.parametrize(
    "text",
    [
        "Dame el resumen de DashNode",
        "Hola, dime el resumen del proyecto DashNode",
        "Hola DashNode asistente, dime el resumen del proyecto de DashNode",
    ],
)
def test_summary_intent_not_unknown(text: str) -> None:
    intent = parse_intent(text, open_project_name=None, last_project_names=[])
    assert intent.intent == IntentType.PROJECT_SUMMARY
    assert intent.project_ref is not None


def test_summary_this_project_open_context() -> None:
    intent = parse_intent(
        "Resume este proyecto",
        open_project_name="DashNode Initial Project",
        last_project_names=[],
    )
    assert intent.intent == IntentType.PROJECT_SUMMARY
    assert intent.project_ref == "DashNode Initial Project"


def test_summary_previous_project_conversational_index() -> None:
    intent = parse_intent(
        "Dame el resumen del proyecto anterior",
        open_project_name=None,
        last_project_names=["DashNode Initial Project", "VozNotAI"],
    )
    assert intent.intent == IntentType.PROJECT_SUMMARY
    assert intent.conversational_index == 0


def test_voice_style_summary_without_gemini(db_session: Session) -> None:
    _seed_dashnode_project(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    answer = orch.answer(
        "Hola DashNode asistente, dime el resumen del proyecto de DashNode",
        "u1",
        "admin",
        None,
    )
    assert "Resumen de DashNode Initial Project" in answer
    assert "Historias de usuario" in answer
    assert "tardó demasiado" not in answer.lower()


def test_summary_unknown_project_clarification(db_session: Session) -> None:
    from app.modules.ai.application.assistant.intent_models import ClarificationNeeded

    _seed_dashnode_project(db_session)
    orch = AssistantOrchestrator(
        db_session, _NoGemini(), _Quota(), AssistantDataService(db_session)
    )
    with pytest.raises(ClarificationNeeded):
        orch.answer("Dame el resumen de ProyectoInexistenteXYZ", "u1", "admin", None)
