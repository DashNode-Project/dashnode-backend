from app.modules.ai.application.assistant.intent_models import IntentType, TaskFilter
from app.modules.ai.application.assistant.intent_parser import parse_intent


def test_list_projects_variants() -> None:
    for text in (
        "¿Cuáles son mis proyectos?",
        "dime cuales son mis proyectos",
        "Cuántos proyectos tengo",
        "proyectos",
        "que proyectos",
        "proyectos disponibles",
        "qué proyectos tengo",
        "Qué proyectos tengo disponibles",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.LIST_PROJECTS, text


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


def test_pending_tasks_in_project() -> None:
    for text in (
        "Qué tengo pendiente en dashnode",
        "qUÉ TENGO PENDIENTE EN DASHNODE",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.LIST_TASKS, text
        assert intent.task_filter == TaskFilter.PENDING
        assert intent.project_ref is not None


def test_count_hus_intent() -> None:
    intent = parse_intent(
        "Cuántas HUs tiene VozNotAI",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.COUNT_PROJECT_HUS


def test_voice_style_stories_with_project() -> None:
    intent = parse_intent(
        "Historias de usuario tiene mi proyecto BOSS ahí",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.LIST_SPRINT_STORIES
    assert intent.project_ref is not None
    assert "boss" in intent.project_ref.lower()


def test_project_summary_phrases() -> None:
    for text in (
        "Dame el resumen de DashNode",
        "Hola, dime el resumen del proyecto DashNode",
        "Hola DashNode asistente, dime el resumen del proyecto de DashNode",
    ):
        intent = parse_intent(text, open_project_name=None, last_project_names=[])
        assert intent.intent == IntentType.PROJECT_SUMMARY, text


def test_stories_this_project() -> None:
    intent = parse_intent(
        "Cuáles son las HUs de este proyecto",
        open_project_name="DashNode Initial Project",
        last_project_names=[],
    )
    assert intent.intent == IntentType.LIST_SPRINT_STORIES
    assert intent.project_ref == "DashNode Initial Project"
