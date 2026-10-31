"""Meetings must not be classified as tasks (regression)."""

from app.modules.ai.application.assistant.intent_models import IntentType, MeetingFilter
from app.modules.ai.application.assistant.intent_parser import parse_intent


def test_pending_meetings_not_tasks() -> None:
    intent = parse_intent(
        "¿Qué reuniones tengo pendientes?",
        open_project_name=None,
        last_project_names=[],
    )
    assert intent.intent == IntentType.LIST_MEETINGS
    assert intent.meeting_filter in {MeetingFilter.USER_PENDING, MeetingFilter.UPCOMING}


def test_project_meetings() -> None:
    intent = parse_intent(
        "¿Qué reuniones tiene VozNotAI?",
        open_project_name=None,
        last_project_names=["VozNotAI"],
    )
    assert intent.intent == IntentType.LIST_MEETINGS
