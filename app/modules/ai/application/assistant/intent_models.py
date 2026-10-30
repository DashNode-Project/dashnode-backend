"""Structured assistant intents (validated, backend-controlled)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    LIST_PROJECTS = "list_projects"
    LIST_PROJECT_MEMBERS = "list_project_members"
    LIST_ALL_PROJECT_MEMBERS = "list_all_project_members"
    ANALYZE_USER_STORIES = "analyze_user_stories"
    REVIEW_USER_STORIES = "review_user_stories"
    IMPROVE_USER_STORIES = "improve_user_stories"
    EXPLAIN_USER_STORY_WRITING = "explain_user_story_writing"
    GENERATE_USER_STORY_EXAMPLES = "generate_user_story_examples"
    PROJECT_ANALYSIS = "project_analysis"
    GEMINI_GROUNDED = "gemini_grounded"
    LIST_SPRINTS = "list_sprints"
    LIST_SPRINT_STORIES = "list_sprint_stories"
    COUNT_PROJECT_HUS = "count_project_hus"
    LIST_TASKS = "list_tasks"
    LIST_DOCUMENTATION = "list_documentation"
    ANALYZE_DOCUMENT = "analyze_document"
    LIST_MEETINGS = "list_meetings"
    COUNT_MEETINGS = "count_meetings"
    PROJECT_FOCUS = "project_focus"
    PROJECT_SUMMARY = "project_summary"
    GREETING = "greeting"
    CHITCHAT = "chitchat"
    UNKNOWN = "unknown"


class TaskFilter(StrEnum):
    PENDING = "pending"
    CORRECTION = "correction"
    BLOCKED = "blocked"
    ASSIGNED_TO_ME = "assigned_to_me"
    UNASSIGNED = "unassigned"
    ALL = "all"


class MeetingFilter(StrEnum):
    ALL = "all"
    UPCOMING = "upcoming"
    PENDING_CONFIRMATION = "pending_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    USER_PENDING = "user_pending"


class ParsedIntent(BaseModel):
    intent: IntentType
    project_ref: str | None = None
    sprint_ref: str | None = None
    task_filter: TaskFilter = TaskFilter.PENDING
    meeting_filter: MeetingFilter = MeetingFilter.UPCOMING
    document_ref: str | None = None
    use_open_project: bool = False
    conversational_index: int | None = Field(default=None, ge=0, le=20)


class ClarificationNeeded(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
