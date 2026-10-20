"""Domain entities for backlog (EP-06)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

FIBONACCI_STORY_POINTS = frozenset({1, 2, 3, 5, 8, 13, 21})


class MoscowPriority(StrEnum):
    MUST_HAVE = "must_have"
    SHOULD_HAVE = "should_have"
    COULD_HAVE = "could_have"
    WONT_HAVE = "wont_have"


class StoryTaskType(StrEnum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    BD = "bd"
    QA = "qa"
    SECURITY = "seguridad"
    DEVOPS = "devops"
    DOCUMENTATION = "documentacion"
    UX_UI = "ux_ui"


class StoryTaskStatus(StrEnum):
    TODO = "todo"


@dataclass
class Epic:
    id: str
    project_id: str
    name: str
    description: str
    color: str | None
    sort_order: int
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass
class UserStory:
    id: str
    epic_id: str
    project_id: str
    title: str
    user_role: str
    reason: str
    acceptance_criteria: str
    moscow_priority: MoscowPriority
    story_points: int | None
    sprint_id: str | None
    sort_order: int
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass
class StoryTask:
    id: str
    user_story_id: str
    project_id: str
    name: str
    task_type: StoryTaskType
    notes: str
    status: StoryTaskStatus
    assignee_id: str | None
    estimated_hours: Decimal | None
    created_by: str
    created_at: datetime
    updated_at: datetime
