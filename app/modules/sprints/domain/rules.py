"""Validation rules for sprint forms."""

from datetime import date

from app.modules.sprints.domain import messages


def validate_create_sprint(
    *,
    name: str,
    goal: str | None,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, str]:
    fields: dict[str, str] = {}
    trimmed = name.strip()
    if not trimmed or len(trimmed) > 100:
        fields["name"] = messages.SPRINT_NAME_REQUIRED
    if start_date is None:
        fields["start_date"] = messages.SPRINT_START_REQUIRED
    if end_date is None:
        fields["end_date"] = messages.SPRINT_END_REQUIRED
    if start_date is not None and end_date is not None and end_date <= start_date:
        fields["end_date"] = messages.SPRINT_END_AFTER_START
    if goal is not None and len(goal.strip()) > 500:
        fields["goal"] = "El objetivo del sprint no puede superar 500 caracteres."
    return fields
