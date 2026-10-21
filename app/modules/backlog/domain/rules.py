"""Validation rules for backlog entities."""

from decimal import Decimal

from app.modules.backlog.domain import messages
from app.modules.backlog.domain.entities import (
    FIBONACCI_STORY_POINTS,
    MoscowPriority,
    StoryTaskType,
)


def validate_epic_name(name: str) -> dict[str, str]:
    clean = name.strip()
    if not clean:
        return {"name": messages.EPIC_NAME_REQUIRED}
    if len(clean) > 100:
        return {"name": messages.EPIC_NAME_REQUIRED}
    return {}


def validate_epic_description(description: str | None) -> dict[str, str]:
    if description is not None and len(description) > 2000:
        return {"description": "La descripción no puede exceder 2000 caracteres."}
    return {}


def validate_story_title(title: str) -> dict[str, str]:
    clean = title.strip()
    if not clean:
        return {"title": messages.STORY_TITLE_REQUIRED}
    if len(clean) > 200:
        return {"title": messages.STORY_TITLE_REQUIRED}
    return {}


def validate_story_role(user_role: str) -> dict[str, str]:
    if not user_role.strip():
        return {"user_role": messages.STORY_ROLE_REQUIRED}
    return {}


def validate_story_reason(reason: str) -> dict[str, str]:
    if not reason.strip():
        return {"reason": messages.STORY_REASON_REQUIRED}
    return {}


def parse_moscow(value: str) -> MoscowPriority | None:
    try:
        return MoscowPriority(value)
    except ValueError:
        return None


def validate_story_points(points: int | None) -> dict[str, str]:
    if points is None:
        return {}
    if points not in FIBONACCI_STORY_POINTS:
        return {"story_points": messages.INVALID_STORY_POINTS}
    return {}


def validate_task_name(name: str) -> dict[str, str]:
    clean = name.strip()
    if not clean:
        return {"name": messages.TASK_NAME_REQUIRED}
    if len(clean) > 200:
        return {"name": messages.TASK_NAME_REQUIRED}
    return {}


def parse_task_type(value: str) -> StoryTaskType | None:
    try:
        return StoryTaskType(value)
    except ValueError:
        return None


def validate_estimated_hours(hours: Decimal | None) -> dict[str, str]:
    if hours is None:
        return {}
    if hours <= 0:
        return {"estimated_hours": messages.ESTIMATED_HOURS_INVALID}
    if hours > 100:
        return {"estimated_hours": "Las horas estimadas no pueden exceder 100."}
    return {}
