"""Unit tests for sprint validation rules."""

from datetime import date

from app.modules.sprints.domain import messages
from app.modules.sprints.domain.rules import validate_create_sprint


def test_validate_create_sprint_end_after_start() -> None:
    fields = validate_create_sprint(
        name="Sprint 1",
        goal=None,
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 10),
    )
    assert fields["end_date"] == messages.SPRINT_END_AFTER_START
