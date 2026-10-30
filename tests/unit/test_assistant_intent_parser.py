from app.modules.ai.application.assistant.intent_models import IntentType, TaskFilter
from app.modules.ai.application.assistant.intent_parser import parse_intent


def test_list_projects_variants() -> None:
    for text in (
        "¿Cuáles son mis proyectos?",
        "dime cuales son mis proyectos",
        "Cuántos proyectos tengo",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.LIST_PROJECTS


def test_chitchat_greeting() -> None:
    intent = parse_intent(
        "Hola, asistente DashNode. ¿Cómo estás?",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.CHITCHAT


def test_tasks_correction_filter() -> None:
    intent = parse_intent(
        "qué tareas están pendientes por corregir",
        open_project_name="DashNode",
        last_project_names=[],
    )
    assert intent.intent == IntentType.LIST_TASKS
    assert intent.task_filter == TaskFilter.CORRECTION


def test_conversational_first_project_members() -> None:
    intent = parse_intent(
        "cuantos miembros tiene el primero",
        open_project_name=None,
        last_project_names=["DashNode", "Otro"],
    )
    assert intent.intent == IntentType.LIST_PROJECT_MEMBERS
    assert intent.conversational_index == 0
