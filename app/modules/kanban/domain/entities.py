"""Kanban domain entities (EP-08)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class KanbanColumnId(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    CODE_REVIEW = "CODE_REVIEW"
    TESTING = "TESTING"
    CORRECTION = "CORRECTION"
    DONE = "DONE"


STANDARD_COLUMNS: list[tuple[KanbanColumnId, str]] = [
    (KanbanColumnId.TODO, "Por hacer"),
    (KanbanColumnId.IN_PROGRESS, "En progreso"),
    (KanbanColumnId.CODE_REVIEW, "Revisión de código"),
    (KanbanColumnId.TESTING, "Pruebas"),
    (KanbanColumnId.CORRECTION, "Corrección"),
    (KanbanColumnId.DONE, "Completada"),
]


@dataclass
class KanbanColumnSettings:
    id: str
    project_id: str
    column_id: KanbanColumnId
    wip_limit: int | None
    updated_at: datetime


@dataclass
class KanbanCard:
    id: str
    title: str
    task_type: str
    status: str
    assignee_id: str | None
    assignee_name: str | None
    assignee_avatar_url: str | None
    user_story_id: str
    user_story_label: str
    user_story_title: str
    estimated_hours: Decimal
    logged_hours: Decimal
    is_blocked: bool
    blocked_reason: str | None
    blocked_by_task_id: str | None
    blocked_by_task_title: str | None
