"""Unit tests for backlog validation rules."""

from decimal import Decimal

from app.modules.backlog.domain import messages
from app.modules.backlog.domain.rules import (
    validate_epic_name,
    validate_estimated_hours,
    validate_story_points,
    validate_story_title,
    validate_task_name,
)


def test_epic_name_required_literal() -> None:
    assert validate_epic_name("") == {"name": messages.EPIC_NAME_REQUIRED}
    assert validate_epic_name("   ") == {"name": messages.EPIC_NAME_REQUIRED}


def test_story_title_required_literal() -> None:
    assert validate_story_title("") == {"title": messages.STORY_TITLE_REQUIRED}


def test_task_name_required_literal() -> None:
    assert validate_task_name("") == {"name": messages.TASK_NAME_REQUIRED}


def test_fibonacci_story_points() -> None:
    assert validate_story_points(5) == {}
    assert validate_story_points(4) == {"story_points": messages.INVALID_STORY_POINTS}


def test_estimated_hours_positive() -> None:
    assert validate_estimated_hours(Decimal("0")) == {
        "estimated_hours": messages.ESTIMATED_HOURS_INVALID
    }
    assert validate_estimated_hours(Decimal("2.5")) == {}
