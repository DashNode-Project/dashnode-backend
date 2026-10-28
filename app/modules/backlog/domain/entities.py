"""Domain entities for backlog (EP-06)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

FIBONACCI_STORY_POINTS = frozenset({1, 2, 3, 5, 8, 13, 21})


class EstimationMode(StrEnum):
    STORY = "story"
    TASK = "task"


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
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    CODE_REVIEW = "CODE_REVIEW"
    TESTING = "TESTING"
    CORRECTION = "CORRECTION"
    DONE = "DONE"


MANUAL_TASK_STATUSES = frozenset(
    {
        StoryTaskStatus.TODO,
        StoryTaskStatus.IN_PROGRESS,
        StoryTaskStatus.CODE_REVIEW,
        StoryTaskStatus.TESTING,
        StoryTaskStatus.DONE,
    }
)


def parse_story_task_status(raw: str) -> StoryTaskStatus | None:
    alias = {"todo": StoryTaskStatus.TODO.value}
    normalized = alias.get(raw, raw)
    try:
        return StoryTaskStatus(normalized)
    except ValueError:
        return None


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
    estimation_mode: EstimationMode
    sprint_id: str | None
    sort_order: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    label: str = ""


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
    story_points: int | None = None
    logged_hours: Decimal = Decimal("0")
    label: str = ""
    is_blocked: bool = False
    blocked_reason: str | None = None
    blocked_by_task_id: str | None = None
