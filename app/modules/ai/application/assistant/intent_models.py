"""Structured assistant intents (validated, backend-controlled)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    LIST_PROJECTS = "list_projects"
    LIST_PROJECT_MEMBERS = "list_project_members"
    LIST_SPRINTS = "list_sprints"
    LIST_SPRINT_STORIES = "list_sprint_stories"
    LIST_TASKS = "list_tasks"
    LIST_DOCUMENTATION = "list_documentation"
    CHITCHAT = "chitchat"
    UNKNOWN = "unknown"


class TaskFilter(StrEnum):
    PENDING = "pending"
    CORRECTION = "correction"
    BLOCKED = "blocked"
    ASSIGNED_TO_ME = "assigned_to_me"
    UNASSIGNED = "unassigned"
    ALL = "all"


class ParsedIntent(BaseModel):
    intent: IntentType
    project_ref: str | None = None
    sprint_ref: str | None = None
    task_filter: TaskFilter = TaskFilter.PENDING
    use_open_project: bool = False
    conversational_index: int | None = Field(default=None, ge=0, le=20)


class ClarificationNeeded(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
